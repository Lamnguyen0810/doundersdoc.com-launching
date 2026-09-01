"""Worker process: `python -m app.worker`. Claims jobs from Postgres and runs them."""
import logging
import time
import traceback

from app.db import SessionLocal, init_db
from app.jobs import claim, fail, finish
from app.llm.review import run_review
from app.models import Document, Review, now
from app.retention import purge_expired

log = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

POLL_SECONDS = 2
PURGE_EVERY_SECONDS = 3600


def handle_review(db, job) -> dict:
    doc = db.get(Document, job.payload["document_id"])
    if not doc or not doc.clauses:
        raise RuntimeError("document missing or not parsed")
    result = run_review(db, job_id=job.id, clauses=doc.clauses, perspective=job.payload["perspective"])
    review = Review(
        document_id=doc.id,
        job_id=job.id,
        perspective=job.payload["perspective"],
        grade=result["grade"],
        letter=result["letter"],
        rubric=result["rubric"],
        issues=result["issues"],
        summary=result["summary"],
        email_draft=result["email_draft"],
    )
    db.add(review)
    db.commit()
    return {"review_id": review.id, "grade": review.grade, "letter": review.letter}


HANDLERS = {"review": handle_review}


def run_forever() -> None:
    init_db()
    last_purge = 0.0
    log.info("worker started")
    while True:
        db = SessionLocal()
        try:
            if time.time() - last_purge > PURGE_EVERY_SECONDS:
                purge_expired(db)
                last_purge = time.time()
            job = claim(db)
            if not job:
                time.sleep(POLL_SECONDS)
                continue
            log.info("job %s %s attempt %s", job.id, job.type, job.attempts)
            handler = HANDLERS.get(job.type)
            if not handler:
                fail(db, job, f"no handler for {job.type}")
                continue
            try:
                finish(db, job, handler(db, job))
                log.info("job %s done in %ss", job.id, (now() - job.locked_at).seconds)
            except Exception as e:  # noqa: BLE001
                log.error("job %s failed: %s", job.id, e)
                fail(db, job, traceback.format_exc())
        finally:
            db.close()


if __name__ == "__main__":
    run_forever()
