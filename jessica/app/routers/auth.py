from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import ANON_COOKIE, SESSION_COOKIE, get_or_create_user, verify_supabase_token
from app.config import settings
from app.db import get_db
from app.models import Document, Workspace
from app.templating import templates

router = APIRouter(prefix="/auth", tags=["auth"])


class SessionIn(BaseModel):
    access_token: str


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
    })


@router.post("/session")
def create_session(body: SessionIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Browser posts the Supabase access token; we verify it and set an httpOnly cookie.
    Any anonymous documents from this browser are re-parented to the user's workspace."""
    try:
        claims = verify_supabase_token(body.access_token)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, "Invalid token") from e
    user = get_or_create_user(db, claims)
    ws = db.query(Workspace).filter_by(owner_id=user.id).first()
    anon = request.cookies.get(ANON_COOKIE)
    if anon and ws:
        db.query(Document).filter_by(anon_id=anon, workspace_id=None).update(
            {"workspace_id": ws.id, "anon_id": None, "expires_at": None}
        )
        db.commit()
    response.set_cookie(SESSION_COOKIE, body.access_token, httponly=True, secure=settings.APP_ENV == "prod",
                        samesite="lax", max_age=60 * 60 * 8)
    return {"ok": True}


@router.post("/logout")
def logout():
    r = RedirectResponse("/", status_code=303)
    r.delete_cookie(SESSION_COOKIE)
    return r
