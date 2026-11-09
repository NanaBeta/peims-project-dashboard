"""Shared project-scoped authorization and transaction metadata helpers."""
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from enterprise.auth import Identity
from enterprise.models import Member, AuditEvent


def membership(db: Session, project_id: str, identity: Identity,
               writable: bool = False, finance: bool = False) -> Member:
    member = db.scalar(select(Member).where(
        Member.project_id == project_id, Member.principal_sub == identity.sub
    ).execution_options(populate_existing=True))
    if member is None:
        # Never disclose a foreign project's existence.
        raise HTTPException(status_code=404, detail='Project not found')
    if finance and member.role != 'manager':
        raise HTTPException(status_code=403, detail='Manager role required')
    if writable and member.role not in {'engineer', 'manager'}:
        raise HTTPException(status_code=403, detail='Engineer or manager role required')
    return member


def audited(db: Session, project_id: str, actor: str, event: str,
            entity_id: str, fields: list[str]):
    db.add(AuditEvent(id=str(uuid4()), project_id=project_id, actor_sub=actor,
                      event_type=event, entity_id=entity_id, changed_fields=fields))
