"""Enforce expires_at: delete the file, keep a tombstone row for the audit trail."""
import logging

from sqlalchemy.orm import Session

from app.models import Document, Message, now
from app.storage import storage

log = logging.getLogger("retention")


def purge_expired(db: Session) -> int:
    docs = db.query(Document).filter(Document.expires_at < now(), Document.deleted_at.is_(None)).all()
    for d in docs:
        purge_document(db, d)
    if docs:
        log.info("purged %d expired documents", len(docs))
    return len(docs)


def purge_document(db: Session, doc: Document) -> None:
    try:
        storage.delete(doc.storage_path)
    except Exception as e:  # noqa: BLE001
        log.warning("could not delete %s: %s", doc.storage_path, e)
    doc.clauses = None
    doc.deleted_at = now()
    db.query(Message).filter_by(document_id=doc.id).delete()
    db.commit()
