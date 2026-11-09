"""PEIMS v0.5: durable project action/document registers and team authorization.

All writes are performed in one DB transaction alongside metadata-only audit events.
Project membership is checked for every request; no unauthenticated demo bypass.
"""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from enterprise.auth import Identity, get_identity
from enterprise.database import get_db
from enterprise.models import Project, Member, ActionItem, DocumentRecord
from enterprise.permissions import membership, audited
from enterprise.schemas import (
    MemberOut, MemberCreate, MemberEdit,
    ActionOut, ActionCreate, ActionEdit,
    DocumentOut, DocumentCreate, DocumentEdit,
)

router = APIRouter(prefix='/v1/projects', tags=['workspace'])


def cleaned(value: str, name: str) -> str:
    val = value.strip()
    if not val:
        raise HTTPException(status_code=422, detail=f'{name} must not be blank')
    return val


def assignee(db: Session, project_id: str, sub: str | None) -> str | None:
    if sub is None or not sub.strip():
        return None
    sub = sub.strip()
    if db.get(Member, (project_id, sub)) is None:
        raise HTTPException(status_code=422, detail='Assigned user must be a project member')
    return sub


def locked_manager(db: Session, project_id: str, identity: Identity):
    """Serialize manager membership mutations on the parent project row in PostgreSQL."""
    membership(db, project_id, identity, finance=True)
    project = db.scalar(select(Project).where(Project.id == project_id).with_for_update())
    if project is None:
        raise HTTPException(status_code=404, detail='Project not found')
    # Recheck after waiting for the parent row lock, so revoked managers cannot write.
    membership(db, project_id, identity, finance=True)
    return project


@router.get('/{project_id}/members', response_model=list[MemberOut])
def list_members(project_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    membership(db, project_id, identity, finance=True)
    return list(db.scalars(select(Member).where(Member.project_id == project_id).order_by(Member.principal_sub)))


@router.post('/{project_id}/members', response_model=MemberOut, status_code=201)
def add_member(project_id: str, payload: MemberCreate, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    locked_manager(db, project_id, identity)
    subject = cleaned(payload.principal_sub, 'principal_sub')
    if db.get(Member, (project_id, subject)) is not None:
        raise HTTPException(status_code=409, detail='Member already exists')
    member = Member(project_id=project_id, principal_sub=subject, role=payload.role, version=1)
    db.add(member)
    audited(db, project_id, identity.sub, 'member.added', subject, ['role'])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Member already exists') from None
    db.refresh(member)
    return member


@router.patch('/{project_id}/members/{principal_sub}', response_model=MemberOut)
def update_member(project_id: str, principal_sub: str, payload: MemberEdit,
                  identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    locked_manager(db, project_id, identity)
    if principal_sub == identity.sub:
        raise HTTPException(status_code=403, detail='Own role cannot be changed through API')
    member = db.get(Member, (project_id, principal_sub))
    if member is None:
        raise HTTPException(status_code=404, detail='Member not found')
    if member.version != payload.expected_version:
        raise HTTPException(status_code=409, detail='Version conflict: reload member')
    if member.role == 'manager' and payload.role != 'manager':
        count = db.scalar(select(func.count()).select_from(Member).where(Member.project_id == project_id,
                                                                         Member.role == 'manager'))
        if count <= 1:
            raise HTTPException(status_code=409, detail='Cannot remove final manager')
    member.role = payload.role
    member.version += 1
    audited(db, project_id, identity.sub, 'member.role_changed', principal_sub, ['role'])
    db.commit(); db.refresh(member)
    return member


@router.delete('/{project_id}/members/{principal_sub}', status_code=204)
def revoke_member(project_id: str, principal_sub: str, expected_version: int = Query(ge=1),
                  identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    locked_manager(db, project_id, identity)
    if principal_sub == identity.sub:
        raise HTTPException(status_code=403, detail='Own membership cannot be revoked through API')
    member = db.get(Member, (project_id, principal_sub))
    if member is None:
        raise HTTPException(status_code=404, detail='Member not found')
    if member.version != expected_version:
        raise HTTPException(status_code=409, detail='Version conflict: reload member')
    if member.role == 'manager':
        count = db.scalar(select(func.count()).select_from(Member).where(Member.project_id == project_id,
                                                                         Member.role == 'manager'))
        if count <= 1:
            raise HTTPException(status_code=409, detail='Cannot remove final manager')
    # Prevent unresolved actions continuing to point at a revoked user.
    if db.scalar(select(func.count()).select_from(ActionItem).where(ActionItem.project_id == project_id,
                                                                     ActionItem.assigned_sub == principal_sub)):
        raise HTTPException(status_code=409, detail='Reassign action items before removing member')
    db.delete(member)
    audited(db, project_id, identity.sub, 'member.revoked', principal_sub, ['membership'])
    db.commit()
    return None


@router.get('/{project_id}/action-items', response_model=list[ActionOut])
def list_actions(project_id: str, limit: int = 100, offset: int = 0,
                 identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    membership(db, project_id, identity)
    if not 1 <= limit <= 200 or not 0 <= offset <= 100000:
        raise HTTPException(status_code=422, detail='Invalid page limits')
    return list(db.scalars(select(ActionItem).where(ActionItem.project_id == project_id)
                           .order_by(ActionItem.reference).limit(limit).offset(offset)))


@router.post('/{project_id}/action-items', response_model=ActionOut, status_code=201)
def add_action(project_id: str, payload: ActionCreate,
               identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    membership(db, project_id, identity, writable=True)
    row = ActionItem(id=str(uuid4()), project_id=project_id,
                     reference=cleaned(payload.reference, 'reference'),
                     summary=cleaned(payload.summary, 'summary'),
                     assigned_sub=assignee(db, project_id, payload.assigned_sub),
                     due_date=payload.due_date, priority=payload.priority, status='open', version=1)
    db.add(row)
    audited(db, project_id, identity.sub, 'action.created', row.id,
            ['reference', 'summary', 'assigned_sub', 'due_date', 'priority', 'status'])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Action reference already exists') from None
    db.refresh(row)
    return row


@router.patch('/{project_id}/action-items/{item_id}', response_model=ActionOut)
def edit_action(project_id: str, item_id: str, payload: ActionEdit,
                identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    membership(db, project_id, identity, writable=True)
    row = db.scalar(select(ActionItem).where(ActionItem.project_id == project_id,
                                              ActionItem.id == item_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail='Action not found')
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail='Version conflict: reload action')
    row.priority, row.status, row.due_date = payload.priority, payload.status, payload.due_date
    row.assigned_sub = assignee(db, project_id, payload.assigned_sub)
    row.version += 1
    audited(db, project_id, identity.sub, 'action.updated', row.id,
            ['priority', 'status', 'due_date', 'assigned_sub'])
    db.commit(); db.refresh(row)
    return row


@router.get('/{project_id}/document-records', response_model=list[DocumentOut])
def list_documents(project_id: str, limit: int = 100, offset: int = 0,
                   identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    membership(db, project_id, identity)
    if not 1 <= limit <= 200 or not 0 <= offset <= 100000:
        raise HTTPException(status_code=422, detail='Invalid page limits')
    return list(db.scalars(select(DocumentRecord).where(DocumentRecord.project_id == project_id)
                           .order_by(DocumentRecord.reference).limit(limit).offset(offset)))


@router.post('/{project_id}/document-records', response_model=DocumentOut, status_code=201)
def add_document(project_id: str, payload: DocumentCreate, identity: Identity = Depends(get_identity),
                 db: Session = Depends(get_db)):
    membership(db, project_id, identity, writable=True)
    row = DocumentRecord(id=str(uuid4()), project_id=project_id,
                         reference=cleaned(payload.reference, 'reference'),
                         title=cleaned(payload.title, 'title'),
                         revision=cleaned(payload.revision, 'revision'), status='draft', version=1)
    db.add(row)
    audited(db, project_id, identity.sub, 'document.created', row.id,
            ['reference', 'title', 'revision', 'status'])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail='Document reference already exists') from None
    db.refresh(row)
    return row


@router.patch('/{project_id}/document-records/{doc_id}', response_model=DocumentOut)
def edit_document(project_id: str, doc_id: str, payload: DocumentEdit,
                  identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    membership(db, project_id, identity, writable=True)
    row = db.scalar(select(DocumentRecord).where(DocumentRecord.project_id == project_id,
                                                 DocumentRecord.id == doc_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail='Document not found')
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail='Version conflict: reload document')
    row.revision = cleaned(payload.revision, 'revision')
    row.status = payload.status
    row.version += 1
    audited(db, project_id, identity.sub, 'document.updated', row.id, ['revision', 'status'])
    db.commit(); db.refresh(row)
    return row


@router.get('/{project_id}/workspace-summary')
def workspace_summary(project_id: str, identity: Identity = Depends(get_identity),
                      db: Session = Depends(get_db)):
    membership(db, project_id, identity)
    actions = dict(db.execute(select(ActionItem.status, func.count()).where(ActionItem.project_id == project_id)
                              .group_by(ActionItem.status)).all())
    documents = dict(db.execute(select(DocumentRecord.status, func.count())
                                .where(DocumentRecord.project_id == project_id)
                                .group_by(DocumentRecord.status)).all())
    return {'project_id': project_id, 'actions': actions, 'documents': documents}
