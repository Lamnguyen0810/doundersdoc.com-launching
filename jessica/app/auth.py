"""
Auth: Supabase issues the JWT (magic link / Google) in the browser; the client posts the
access token to /auth/session and we set an httpOnly cookie. Every request then verifies
that token here. Anonymous visitors get a stable anon_id cookie so they can upload and
review before signing up (documents are re-parented on first login).
"""
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User, Workspace

SESSION_COOKIE = "fd_session"
ANON_COOKIE = "fd_anon"


@dataclass
class Principal:
    user: User | None
    workspace: Workspace | None
    anon_id: str

    @property
    def actor(self) -> str:
        return self.user.id if self.user else self.anon_id

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json")


def verify_supabase_token(token: str) -> dict:
    """Supports both legacy HS256 project secrets and current asymmetric JWKS keys."""
    options = {"verify_aud": False}
    if settings.SUPABASE_JWT_SECRET:
        return jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options=options)
    signing_key = _jwks_client().get_signing_key_from_jwt(token).key
    return jwt.decode(token, signing_key, algorithms=["ES256", "RS256"], options=options)


def ensure_anon_id(request: Request, response: Response | None = None) -> str:
    """Stable per-browser id. New ids are stashed on request.state; the middleware in
    app.main writes the cookie, which also covers routes that return their own Response."""
    anon = request.cookies.get(ANON_COOKIE) or getattr(request.state, "new_anon_id", None)
    if not anon:
        anon = str(uuid.uuid4())
        request.state.new_anon_id = anon
    return anon


def get_or_create_user(db: Session, claims: dict) -> User:
    uid, email = claims["sub"], claims.get("email", "")
    user = db.get(User, uid)
    if not user:
        user = User(id=uid, email=email)
        db.add(user)
        db.add(Workspace(name=email.split("@")[0] or "My workspace", owner_id=uid))
        db.commit()
    return user


def current_principal(request: Request, response: Response, db: Session = Depends(get_db)) -> Principal:
    anon_id = ensure_anon_id(request, response)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return Principal(user=None, workspace=None, anon_id=anon_id)
    try:
        claims = verify_supabase_token(token)
    except jwt.PyJWTError:
        response.delete_cookie(SESSION_COOKIE)
        return Principal(user=None, workspace=None, anon_id=anon_id)
    user = get_or_create_user(db, claims)
    workspace = db.query(Workspace).filter_by(owner_id=user.id).first()
    return Principal(user=user, workspace=workspace, anon_id=anon_id)


def require_user(p: Principal = Depends(current_principal)) -> Principal:
    if not p.is_authenticated:
        raise HTTPException(status_code=401, detail="Sign in required")
    return p
