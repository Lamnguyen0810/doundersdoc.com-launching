import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.auth import ANON_COOKIE
from app.config import settings
from app.db import init_db
from app.routers import auth, documents, pages

logging.basicConfig(level=logging.INFO)

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV, traces_sample_rate=0.1)



@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.APP_ENV == "dev":
        init_db()  # production: alembic upgrade head
    yield


app = FastAPI(title="Jessica — FD AI", version="0.1.0", lifespan=lifespan,
              docs_url="/api/docs" if settings.APP_ENV != "prod" else None)


@app.middleware("http")
async def anon_cookie(request: Request, call_next):
    response = await call_next(request)
    new_anon = getattr(request.state, "new_anon_id", None)
    if new_anon and ANON_COOKIE not in request.cookies:
        response.set_cookie(ANON_COOKIE, new_anon, httponly=True, samesite="lax",
                            secure=settings.APP_ENV == "prod", max_age=60 * 60 * 24 * 30)
    return response

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(documents.router)
