from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import Principal, current_principal
from app.db import get_db
from app.models import Document
from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def home(request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    q = db.query(Document).filter(Document.deleted_at.is_(None))
    q = q.filter_by(workspace_id=p.workspace.id) if p.workspace else q.filter_by(anon_id=p.anon_id, workspace_id=None)
    docs = q.order_by(Document.created_at.desc()).limit(20).all()
    return templates.TemplateResponse(request, "index.html", {"docs": docs, "principal": p})


@router.get("/health")
def health():
    return {"ok": True}
