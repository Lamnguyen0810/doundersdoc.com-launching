from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, actor: str, action: str, object_type: str, object_id: str, ip: str | None = None) -> None:
    db.add(AuditLog(actor=actor, action=action, object_type=object_type, object_id=object_id, ip=ip))
