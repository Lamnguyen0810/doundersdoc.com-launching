"""
FD AI — DEMO MODE.  One process, no database, no Supabase, no Stripe.

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...      # omit to see a canned review instead
    uvicorn demo:app --reload                # http://localhost:8000

Everything lives in memory and disappears on restart. This reuses the real parser and the real
review pipeline (app/parsing.py, app/llm/review.py); only persistence and auth are stubbed.
"""
import json
import threading
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.docx_out import markdown_to_docx
from app.llm.chat import stream_reply
from app.parsing import parse

app = FastAPI(title="FD AI — demo")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "demo" / "templates"))

DOCS: dict[str, dict] = {}
REVIEWS: dict[str, dict] = {}
JOBS: dict[str, dict] = {}
CHATS: dict[str, dict] = {}   # {id, document_id|None, messages:[{role, content}], created_at}
LOCK = threading.Lock()

CANNED = json.loads((Path(__file__).parent / "demo" / "canned_review.json").read_text())


def now() -> str:
    return datetime.now(UTC).strftime("%d %b %Y %H:%M")


def run_job(job_id: str) -> None:
    job = JOBS[job_id]
    doc = DOCS[job["document_id"]]
    try:
        with LOCK:
            job["status"] = "running"
        if settings.ANTHROPIC_API_KEY:
            from app.llm.review import run_review

            result = run_review(None, job_id=job_id, clauses=doc["clauses"], perspective=job["perspective"])
        else:
            result = dict(CANNED)  # no key: show what the output looks like
            result["summary"] = "(Canned demo output — set ANTHROPIC_API_KEY for a live review.) " + result["summary"]
        review_id = str(uuid.uuid4())
        REVIEWS[review_id] = {**result, "id": review_id, "document_id": doc["id"],
                              "perspective": job["perspective"], "created_at": now()}
        with LOCK:
            job.update(status="done", result={"review_id": review_id, "grade": result["grade"],
                                             "letter": result["letter"]})
    except Exception:  # noqa: BLE001
        with LOCK:
            job.update(status="failed", error=traceback.format_exc())


@app.get("/", response_class=HTMLResponse)
def site(request: Request):
    """Founders Doc marketing site (Mockup E). Every 'Launch FD AI' button goes to /fd-ai."""
    return templates.TemplateResponse(request, "site.html", {})


@app.get("/fd-ai", response_class=HTMLResponse)
def landing(request: Request):
    """The FD AI landing page, with its dropzone posting to /documents."""
    return templates.TemplateResponse(request, "landing.html", {})


@app.get("/app", response_class=HTMLResponse)
def home(request: Request):
    docs = sorted(DOCS.values(), key=lambda d: d["created_at"], reverse=True)
    return templates.TemplateResponse(request, "index.html", {"docs": docs, "live": bool(settings.ANTHROPIC_API_KEY)})


@app.post("/documents")
async def upload(file: UploadFile = File(...), perspective: str = Form("the company")):
    data = await file.read()
    try:
        clauses, pages = parse(data, file.content_type or "", file.filename or "upload")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not clauses:
        raise HTTPException(400, "No readable text found in the document")
    doc_id = str(uuid.uuid4())
    DOCS[doc_id] = {"id": doc_id, "filename": file.filename, "clauses": clauses, "pages": pages,
                    "created_at": now()}
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"id": job_id, "document_id": doc_id, "perspective": perspective, "status": "queued"}
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return RedirectResponse(f"/documents/{doc_id}?job={job_id}", status_code=303)


@app.post("/demo/sample")
def use_sample():
    """One click: load the bundled adviser agreement and review it for the company."""
    sample = Path(__file__).parent / "demo" / "sample_adviser_agreement.docx"
    clauses, _ = parse(sample.read_bytes(), "", sample.name)
    doc_id = str(uuid.uuid4())
    DOCS[doc_id] = {"id": doc_id, "filename": sample.name, "clauses": clauses, "pages": None, "created_at": now()}
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"id": job_id, "document_id": doc_id, "status": "queued",
                    "perspective": "the company (the startup granting the options)"}
    threading.Thread(target=run_job, args=(job_id,), daemon=True).start()
    return RedirectResponse(f"/documents/{doc_id}?job={job_id}", status_code=303)


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
def document(doc_id: str, request: Request, job: str | None = None):
    doc = DOCS.get(doc_id)
    if not doc:
        raise HTTPException(404)
    reviews = [r for r in REVIEWS.values() if r["document_id"] == doc_id]
    return templates.TemplateResponse(request, "document.html", {"doc": doc, "reviews": reviews, "job_id": job})


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_status(job_id: str, request: Request):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "job_status.html", {"job": job})


@app.get("/reviews/{review_id}", response_class=HTMLResponse)
def review(review_id: str, request: Request):
    r = REVIEWS.get(review_id)
    if not r:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "review.html", {"review": r, "doc": DOCS[r["document_id"]]})


# ---------------------------------------------------------------------------
# FD AI chat — free-form: review, draft, ask, in one conversation
# ---------------------------------------------------------------------------

def _new_chat(document_id: str | None = None, opener: str | None = None) -> dict:
    cid = str(uuid.uuid4())
    CHATS[cid] = {"id": cid, "document_id": document_id, "messages": [], "created_at": now()}
    if opener:
        CHATS[cid]["opener"] = opener
    return CHATS[cid]


@app.get("/chat", response_class=HTMLResponse)
def chat_index(doc: str | None = None, prompt: str | None = None):
    """Start a conversation, optionally attached to a document or seeded with a prompt."""
    chat = _new_chat(doc if doc in DOCS else None, prompt)
    return RedirectResponse(f"/chat/{chat['id']}", status_code=303)


@app.get("/chat/{chat_id}", response_class=HTMLResponse)
def chat_page(chat_id: str, request: Request):
    chat = CHATS.get(chat_id)
    if not chat:
        raise HTTPException(404)
    doc = DOCS.get(chat["document_id"]) if chat["document_id"] else None
    docs = sorted(DOCS.values(), key=lambda d: d["created_at"], reverse=True)
    chats = sorted(CHATS.values(), key=lambda c: c["created_at"], reverse=True)
    return templates.TemplateResponse(request, "chat.html", {
        "chat": chat, "doc": doc, "docs": docs, "chats": chats, "live": bool(settings.ANTHROPIC_API_KEY),
        "opener": chat.pop("opener", None),
    })


def chat_title(chat: dict) -> str:
    for m in chat["messages"]:
        if m["role"] == "user":
            t = m["content"].strip().splitlines()[0]
            return (t[:38] + "…") if len(t) > 40 else t
    return "New conversation"


templates.env.globals["chat_title"] = chat_title


@app.post("/chat/{chat_id}/delete")
def chat_delete(chat_id: str):
    CHATS.pop(chat_id, None)
    return RedirectResponse("/chat", status_code=303)


@app.post("/chat/{chat_id}/attach")
def chat_attach(chat_id: str, document_id: str = Form("")):
    chat = CHATS.get(chat_id)
    if not chat:
        raise HTTPException(404)
    chat["document_id"] = document_id if document_id in DOCS else None
    return RedirectResponse(f"/chat/{chat_id}", status_code=303)


@app.post("/chat/{chat_id}/upload")
async def chat_upload(chat_id: str, file: UploadFile = File(...)):
    """Attach a new document to the conversation without leaving it."""
    chat = CHATS.get(chat_id)
    if not chat:
        raise HTTPException(404)
    data = await file.read()
    clauses, pages = parse(data, file.content_type or "", file.filename or "upload")
    doc_id = str(uuid.uuid4())
    DOCS[doc_id] = {"id": doc_id, "filename": file.filename, "clauses": clauses, "pages": pages, "created_at": now()}
    chat["document_id"] = doc_id
    return RedirectResponse(f"/chat/{chat_id}", status_code=303)


@app.post("/chat/{chat_id}/message")
def chat_message(chat_id: str, message: str = Form(...)):
    """Streams FD AI's reply as plain text chunks; the page appends them as they arrive."""
    chat = CHATS.get(chat_id)
    if not chat:
        raise HTTPException(404)
    doc = DOCS.get(chat["document_id"]) if chat["document_id"] else None
    chat["messages"].append({"role": "user", "content": message})

    def gen():
        parts: list[str] = []
        try:
            for chunk in stream_reply(chat["messages"], doc["clauses"] if doc else None):
                parts.append(chunk)
                yield chunk
        except Exception as e:  # noqa: BLE001
            err = f"\n\n[FD AI could not answer: {e}]"
            parts.append(err)
            yield err
        chat["messages"].append({"role": "assistant", "content": "".join(parts)})

    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.get("/chat/{chat_id}/download/{index}")
def chat_download(chat_id: str, index: int):
    """Export one assistant message (a draft) as .docx."""
    chat = CHATS.get(chat_id)
    if not chat or index >= len(chat["messages"]) or chat["messages"][index]["role"] != "assistant":
        raise HTTPException(404)
    md = chat["messages"][index]["content"]
    title = next((ln.lstrip("# ").strip() for ln in md.splitlines() if ln.startswith("# ")), "FD AI draft")
    safe = "".join(ch for ch in title if ch.isalnum() or ch in " -_")[:60].strip() or "FD-AI-draft"
    return Response(markdown_to_docx(md, title), media_type=(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        headers={"Content-Disposition": f'attachment; filename="{safe}.docx"'})
