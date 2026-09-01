"""Postgres-as-queue. One worker process claims jobs with SKIP LOCKED; no Redis."""
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Job, now

STALE_AFTER = timedelta(minutes=10)
MAX_ATTEMPTS = 3


def enqueue(db: Session, type_: str, payload: dict) -> Job:
    job = Job(type=type_, payload=payload)
    db.add(job)
    db.commit()
    return job


def claim(db: Session) -> Job | None:
    """Atomically claim the oldest queued job (or a stale running one)."""
    stale = now() - STALE_AFTER
    if settings.is_sqlite:
        job = db.execute(
            select(Job)
            .where((Job.status == "queued") | ((Job.status == "running") & (Job.locked_at < stale)))
            .order_by(Job.created_at)
            .limit(1)
        ).scalar_one_or_none()
        if not job:
            return None
    else:
        row = db.execute(
            text(
                """
                UPDATE jobs SET status='running', locked_at=now(), attempts=attempts+1
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE status='queued' OR (status='running' AND locked_at < :stale)
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING id
                """
            ),
            {"stale": stale},
        ).first()
        db.commit()
        if not row:
            return None
        return db.get(Job, row[0])
    job.status, job.locked_at, job.attempts = "running", now(), job.attempts + 1
    db.commit()
    return job


def finish(db: Session, job: Job, result: dict) -> None:
    job.status, job.result, job.finished_at = "done", result, now()
    db.commit()


def fail(db: Session, job: Job, error: str) -> None:
    job.error = error[:4000]
    job.status = "failed" if job.attempts >= MAX_ATTEMPTS else "queued"
    job.locked_at = None
    db.commit()
