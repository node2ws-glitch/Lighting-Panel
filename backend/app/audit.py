from sqlalchemy.orm import Session
from app.models import AuditEvent, User

def record_event(db: Session, action: str, actor: User | None = None, detail: str = '') -> None:
    db.add(AuditEvent(actor_id=actor.id if actor else None, action=action, detail=detail[:2000]))
