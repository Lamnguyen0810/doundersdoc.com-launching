import hashlib
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.audit import log
from app.auth import Principal, current_principal
from app.config import settings
from app.db import get_db
from app.jobs import enqueue
from app.models import Document, Job, Message, Review, now
from app.parsing import parse
from app.retention import purge_document
from app.storage import storage
from app.templating import templates

router = APIRouter(tags=["documents"])


def owned_document(doc_id: str, p: Principal, db: Session) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.deleted_at:
        raise HTTPException(404, "Document not found")
    owns_ws = p.workspace is not None and doc.workspace_id == p.workspace.id
    owns_anon = doc.workspace_id is None and doc.anon_id == p.anon_id
    owns = owns_ws or owns_anon
    if not owns:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("/documents")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    perspective: str = Form("the party receiving this document"),
    p: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.MAX_UPLOAD_MB} MB")
    try:
        clauses, pages = parse(data, file.content_type or "", file.filename or "upload")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not clauses:
        raise HTTPException(400, "No readable text found in the document")

    doc = Document(
        workspace_id=p.workspace.id if p.workspace else None,
        anon_id=None if p.workspace else p.anon_id,
        filename=file.filename or "upload",
        mime=file.content_type or "application/octet-stream",
        storage_path="",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        page_count=pages,
        clauses=clauses,
        expires_at=now() + (timedelta(days=settings.DOCUMENT_RETENTION_DAYS) if p.workspace
                            else timedelta(hours=settings.ANON_RETENTION_HOURS)),
    )
    db.add(doc)
    db.flush()
    owner = doc.workspace_id or doc.anon_id
    doc.storage_path = f"{owner}/{doc.id}/{doc.filename}"
    storage.put(doc.storage_path, data, doc.mime)
    log(db, p.actor, "upload", "document", doc.id, request.client.host if request.client else None)

    job = enqueue(db, "review", {"document_id": doc.id, "perspective": perspective})
    db.commit()
    return RedirectResponse(f"/documents/{doc.id}?job={job.id}", status_code=303)


@router.get("/documents/{doc_id}", response_class=HTMLResponse)
def document_page(doc_id: str, request: Request, job: str | None = None,
                  p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    doc = owned_document(doc_id, p, db)
    reviews = db.query(Review).filter_by(document_id=doc.id).order_by(Review.created_at.desc()).all()
    messages = db.query(Message).filter_by(document_id=doc.id).order_by(Message.created_at).all()
    return templates.TemplateResponse(request, "document.html", {
        "doc": doc, "reviews": reviews, "messages": messages, "job_id": job, "principal": p,
    })


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_status(job_id: str, request: Request, p: Principal = Depends(current_principal),
               db: Session = Depends(get_db)):
    """HTMX polls this; returns a fragment. When done it swaps in the review link."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404)
    owned_document(job.payload.get("document_id", ""), p, db)
    return templates.TemplateResponse(request, "partials/job_status.html", {"job": job})


@router.get("/reviews/{review_id}", response_class=HTMLResponse)
def review_page(review_id: str, request: Request, p: Principal = Depends(current_principal),
                db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(404)
    doc = owned_document(review.document_id, p, db)
    log(db, p.actor, "view", "review", review.id)
    db.commit()
    return templates.TemplateResponse(request, "review.html", {"review": review, "doc": doc, "principal": p})


@router.post("/documents/{doc_id}/ask", response_class=HTMLResponse)
def ask(doc_id: str, request: Request, question: str = Form(...),
        p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """Synchronous for now (answers arrive in seconds); move to a job if latency grows."""
    from app.llm.ask import answer

    doc = owned_document(doc_id, p, db)
    if not p.is_authenticated:
        raise HTTPException(401, "Sign in to ask questions")
    history = [{"role": m.role, "content": m.content}
               for m in db.query(Message).filter_by(document_id=doc.id).order_by(Message.created_at).all()]
    reply = answer(db, job_id=None, clauses=doc.clauses, history=history, question=question)
    db.add_all([Message(document_id=doc.id, role="user", content=question),
                Message(document_id=doc.id, role="assistant", content=reply)])
    db.commit()
    return templates.TemplateResponse(request, "partials/ask_turn.html", {"question": question, "reply": reply})


@router.post("/documents/{doc_id}/delete")
def delete_document(doc_id: str, request: Request, p: Principal = Depends(current_principal),
                    db: Session = Depends(get_db)):
    doc = owned_document(doc_id, p, db)
    purge_document(db, doc)
    log(db, p.actor, "delete", "document", doc.id)
    db.commit()
    return RedirectResponse("/", status_code=303)
