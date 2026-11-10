"""Durable, authenticated v0.8 project work management API.

A separate deployment from Streamlit; no implicit demo-data sync or global
sharing. Every query is project scoped; permissions are rechecked on request.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, func, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise.auth import Identity, get_identity
from enterprise.database import get_db
from enterprise.models import (
    Project, Member, WorkItem, WorkDependency, WorkTimeEntry, WorkComment,
    utc_now,
)
from enterprise.permissions import membership, audited

router = APIRouter(prefix='/v1/projects', tags=['work-management'])

# Typed, bounded domain values: no arbitrary workflow expression evaluation.
class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkItemOut(RecordOut):
    id: str
    project_id: str
    reference: str
    title: str
    description: str
    kind: str
    parent_id: str | None
    status: str
    priority: str
    assigned_sub: str | None
    start_date: date
    due_date: date
    estimate_hours: Decimal
    progress_pct: Decimal
    version: int
    created_by: str
    updated_by: str


class WorkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    kind: str = Field(default='task', pattern=r'^(task|subtask|milestone)$')
    parent_id: str | None = Field(default=None, max_length=36)
    assigned_sub: str | None = Field(default=None, max_length=255)
    status: str = Field(default='todo', pattern=r'^(todo|in_progress|blocked|done)$')
    priority: str = Field(default='medium', pattern=r'^(low|medium|high|critical)$')
    start_date: date
    due_date: date
    estimate_hours: Decimal = Field(default=Decimal('0'), ge=0, max_digits=10, decimal_places=2)
    progress_pct: Decimal = Field(default=Decimal('0'), ge=0, le=100, max_digits=5, decimal_places=2)

    @field_validator('reference', 'title')
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Cannot be blank')
        return value

    @field_validator('description')
    @classmethod
    def trim_description(cls, value: str) -> str:
        return value.strip()

    @field_validator('assigned_sub', 'parent_id')
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode='after')
    def consistent(self):
        if self.due_date < self.start_date:
            raise ValueError('Due date must not precede start date')
        if self.kind == 'subtask' and not self.parent_id:
            raise ValueError('Subtask must specify an existing parent task')
        if self.kind != 'subtask' and self.parent_id:
            raise ValueError('Only subtasks can have a parent task')
        if self.kind == 'milestone' and (self.start_date != self.due_date or self.estimate_hours != 0):
            raise ValueError('Milestone must have one date and zero estimated hours')
        if self.status == 'done' and self.progress_pct != 100:
            raise ValueError('Completed items require 100% progress')
        return self


class WorkEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    assigned_sub: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern=r'^(todo|in_progress|blocked|done)$')
    priority: str | None = Field(default=None, pattern=r'^(low|medium|high|critical)$')
    start_date: date | None = None
    due_date: date | None = None
    estimate_hours: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    progress_pct: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)

    @model_validator(mode='after')
    def not_empty(self):
        if self.model_fields_set <= {'expected_version'}:
            raise ValueError('Specify at least one field to update')
        return self


class PredecessorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    predecessor_id: str = Field(min_length=1, max_length=36)


class DependencyOut(RecordOut):
    id: str
    predecessor_id: str
    successor_id: str
    created_by: str


class TimeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_date: date
    hours: Decimal = Field(gt=0, le=24, max_digits=5, decimal_places=2)
    note: str = Field(default='', max_length=500)


class TimeOut(RecordOut):
    id: str
    work_item_id: str
    actor_sub: str
    work_date: date
    hours: Decimal
    note: str


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=2000)

    @field_validator('body')
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Comment must not be blank')
        return value


class CommentOut(RecordOut):
    id: str
    work_item_id: str
    author_sub: str
    body: str
    created_at: datetime


def _page(limit: int, offset: int):
    if not 1 <= limit <= 200 or not 0 <= offset <= 100000:
        raise HTTPException(status_code=422, detail='Invalid page limits')


def _work(db: Session, project_id: str, item_id: str, *, locked: bool = False) -> WorkItem:
    statement = select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    if locked:
        statement = statement.with_for_update()
    row = db.scalar(statement)
    if row is None:
        raise HTTPException(status_code=404, detail='Work item not found')
    return row


def _assignee(db: Session, project_id: str, sub: str | None) -> str | None:
    if sub is None:
        return None
    if len(sub) > 255 or not sub.strip():
        raise HTTPException(status_code=422, detail='Invalid assignee')
    # Project membership, not a tenant-level directory suggestion, grants access.
    row = db.get(Member, (project_id, sub))
    if row is None or row.role not in {'engineer','manager'}:
        raise HTTPException(status_code=422, detail='Assignee must be an engineer or manager on this project')
    return sub


def _parent(db: Session, project_id: str, parent_id: str | None):
    if parent_id is None:
        return None
    row = db.scalar(select(WorkItem).where(WorkItem.id == parent_id, WorkItem.project_id == project_id))
    if row is None or row.kind != 'task':
        raise HTTPException(status_code=422, detail='Parent must be a task in this project')
    return row


def _clean_update(row: WorkItem, payload: WorkEdit) -> dict:
    data = dict(reference=row.reference, title=row.title, description=row.description,
                kind=row.kind, parent_id=row.parent_id, assigned_sub=row.assigned_sub,
                status=row.status, priority=row.priority, start_date=row.start_date,
                due_date=row.due_date, estimate_hours=row.estimate_hours,
                progress_pct=row.progress_pct)
    for key in payload.model_fields_set - {'expected_version'}:
        value = getattr(payload, key)
        if value is None and key != 'assigned_sub':
            raise HTTPException(status_code=422, detail=f'{key} cannot be null')
        data[key] = value
    if data['status'] == 'done' and 'progress_pct' not in payload.model_fields_set:
        data['progress_pct'] = Decimal('100')
    # Revalidate the *complete* record, including unchanged fields.
    try:
        return WorkCreate.model_validate(data).model_dump()
    except Exception:
        raise HTTPException(status_code=422, detail='Inconsistent task fields; check dates, milestone and completion') from None


def _cycle(edges: list[tuple[str,str]], predecessor: str, successor: str) -> bool:
    """Would adding predecessor→successor create a directed dependency cycle?"""
    graph: dict[str, set[str]] = {}
    for a,b in edges:
        graph.setdefault(a,set()).add(b)
    stack=[successor]
    seen=set()
    while stack:
        curr=stack.pop()
        if curr == predecessor:
            return True
        if curr not in seen:
            seen.add(curr)
            stack.extend(graph.get(curr,()))
    return False


@router.get('/{project_id}/work-items', response_model=list[WorkItemOut])
def list_work_items(project_id: str, limit: int = Query(default=100,ge=1,le=200),
                    offset: int = Query(default=0,ge=0,le=100000),
                    status: str | None = Query(default=None,pattern=r'^(todo|in_progress|blocked|done)$'),
                    identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    membership(db,project_id,identity)
    statement=select(WorkItem).where(WorkItem.project_id==project_id)
    if status is not None:
        statement=statement.where(WorkItem.status==status)
    return list(db.scalars(statement.order_by(WorkItem.reference,WorkItem.id).limit(limit).offset(offset)))


@router.post('/{project_id}/work-items', response_model=WorkItemOut, status_code=201)
def create_work_item(project_id: str,payload:WorkCreate,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    fields=payload.model_dump()
    fields['assigned_sub']=_assignee(db,project_id,fields['assigned_sub'])
    _parent(db,project_id,fields['parent_id'])
    row=WorkItem(id=str(uuid4()),project_id=project_id,**fields,
                 version=1,created_by=identity.sub,updated_by=identity.sub)
    db.add(row)
    audited(db,project_id,identity.sub,'work.created',row.id,list(fields))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,detail='Work item reference already exists or a linked record changed') from None
    db.refresh(row)
    return row


@router.get('/{project_id}/work-items/{item_id}',response_model=WorkItemOut)
def get_work_item(project_id:str,item_id:str,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    return _work(db,project_id,item_id)


@router.patch('/{project_id}/work-items/{item_id}',response_model=WorkItemOut)
def edit_work_item(project_id:str,item_id:str,payload:WorkEdit,
                   identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    row=_work(db,project_id,item_id,locked=True)
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409,detail='Version conflict: reload work item')
    fields=_clean_update(row,payload)
    fields['assigned_sub']=_assignee(db,project_id,fields['assigned_sub'])
    changed=[]
    for key in payload.model_fields_set - {'expected_version'}:
        if getattr(row,key) != fields[key]:
            changed.append(key)
    if row.status != fields['status'] and fields['status']=='done' and 'progress_pct' not in changed:
        changed.append('progress_pct')
    for key in set(fields) - {'reference','parent_id','kind'}:
        setattr(row,key,fields[key])
    row.version+=1
    row.updated_by=identity.sub
    row.updated_at=utc_now()
    audited(db,project_id,identity.sub,'work.updated',row.id,changed)
    db.commit();db.refresh(row)
    return row


@router.get('/{project_id}/work-items/{item_id}/predecessors',response_model=list[DependencyOut])
def list_predecessors(project_id:str,item_id:str,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    _work(db,project_id,item_id)
    return list(db.scalars(select(WorkDependency).where(WorkDependency.project_id==project_id,
           WorkDependency.successor_id==item_id).order_by(WorkDependency.id)))


@router.post('/{project_id}/work-items/{item_id}/predecessors',response_model=DependencyOut,status_code=201)
def add_predecessor(project_id:str,item_id:str,payload:PredecessorCreate,
                    identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    # On PostgreSQL this project lock serializes dependency graph changes.
    db.scalar(select(Project).where(Project.id==project_id).with_for_update())
    _work(db,project_id,item_id)
    _work(db,project_id,payload.predecessor_id)
    if item_id==payload.predecessor_id:
        raise HTTPException(status_code=422,detail='Task cannot depend on itself')
    edges=list(db.execute(select(WorkDependency.predecessor_id,WorkDependency.successor_id)
                          .where(WorkDependency.project_id==project_id)).all())
    if (payload.predecessor_id,item_id) in edges:
        raise HTTPException(status_code=409,detail='Dependency already exists')
    if _cycle(edges,payload.predecessor_id,item_id):
        raise HTTPException(status_code=422,detail='Dependency would create a cycle')
    row=WorkDependency(id=str(uuid4()),project_id=project_id,
       predecessor_id=payload.predecessor_id,successor_id=item_id,created_by=identity.sub)
    db.add(row)
    audited(db,project_id,identity.sub,'work.dependency_added',item_id,['predecessor_id'])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,detail='Dependency changed concurrently') from None
    db.refresh(row)
    return row


@router.delete('/{project_id}/work-items/{item_id}/predecessors/{predecessor_id}',status_code=204)
def remove_predecessor(project_id:str,item_id:str,predecessor_id:str,
                       identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    db.scalar(select(Project).where(Project.id==project_id).with_for_update())
    row=db.scalar(select(WorkDependency).where(WorkDependency.project_id==project_id,
           WorkDependency.successor_id==item_id,WorkDependency.predecessor_id==predecessor_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404,detail='Dependency not found')
    db.delete(row)
    audited(db,project_id,identity.sub,'work.dependency_removed',item_id,['predecessor_id'])
    db.commit()
    return None


@router.get('/{project_id}/work-items/{item_id}/time-entries',response_model=list[TimeOut])
def list_time_entries(project_id:str,item_id:str,limit:int=Query(default=100,ge=1,le=200),
                      offset:int=Query(default=0,ge=0,le=100000),
                      identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    _work(db,project_id,item_id)
    return list(db.scalars(select(WorkTimeEntry).where(WorkTimeEntry.project_id==project_id,
           WorkTimeEntry.work_item_id==item_id).order_by(WorkTimeEntry.created_at,WorkTimeEntry.id)
           .limit(limit).offset(offset)))


@router.post('/{project_id}/work-items/{item_id}/time-entries',response_model=TimeOut,status_code=201)
def add_time_entry(project_id:str,item_id:str,payload:TimeCreate,
                   identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    # Serialize daily hour totals with the same project lock, on PostgreSQL.
    db.scalar(select(Project).where(Project.id==project_id).with_for_update())
    _work(db,project_id,item_id)
    daily=db.scalar(select(func.coalesce(func.sum(WorkTimeEntry.hours),0)).where(
        WorkTimeEntry.project_id==project_id,WorkTimeEntry.actor_sub==identity.sub,
        WorkTimeEntry.work_date==payload.work_date))
    if Decimal(str(daily))+payload.hours > Decimal('24'):
        raise HTTPException(status_code=422,detail='Logged time cannot exceed 24 hours per person per project per day')
    row=WorkTimeEntry(id=str(uuid4()),project_id=project_id,work_item_id=item_id,
       actor_sub=identity.sub,work_date=payload.work_date,hours=payload.hours,note=payload.note.strip())
    db.add(row)
    audited(db,project_id,identity.sub,'work.time_logged',item_id,['work_date','hours'])
    db.commit();db.refresh(row)
    return row


@router.get('/{project_id}/work-items/{item_id}/comments',response_model=list[CommentOut])
def list_comments(project_id:str,item_id:str,limit:int=Query(default=100,ge=1,le=200),
                  offset:int=Query(default=0,ge=0,le=100000),
                  identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    _work(db,project_id,item_id)
    return list(db.scalars(select(WorkComment).where(WorkComment.project_id==project_id,
           WorkComment.work_item_id==item_id).order_by(WorkComment.created_at,WorkComment.id)
           .limit(limit).offset(offset)))


@router.post('/{project_id}/work-items/{item_id}/comments',response_model=CommentOut,status_code=201)
def post_comment(project_id:str,item_id:str,payload:CommentCreate,
                 identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    _work(db,project_id,item_id)
    row=WorkComment(id=str(uuid4()),project_id=project_id,work_item_id=item_id,
                    author_sub=identity.sub,body=payload.body)
    db.add(row)
    audited(db,project_id,identity.sub,'work.comment_added',item_id,['body'])
    db.commit();db.refresh(row)
    return row


@router.get('/{project_id}/work-summary')
def work_summary(project_id:str,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    is_open = WorkItem.status != 'done'
    is_overdue = is_open & (WorkItem.due_date < date.today())
    total, open_count, overdue, milestones = db.execute(select(
        func.count(WorkItem.id),
        func.coalesce(func.sum(case((is_open, 1), else_=0)), 0),
        func.coalesce(func.sum(case((is_overdue, 1), else_=0)), 0),
        func.coalesce(func.sum(case((WorkItem.kind == 'milestone', 1), else_=0)), 0),
    ).where(WorkItem.project_id == project_id)).one()
    hours = db.scalar(select(func.coalesce(func.sum(WorkTimeEntry.hours), 0)).where(
        WorkTimeEntry.project_id == project_id))
    return {
      'project_id': project_id,
      'total': int(total),
      'open': int(open_count),
      'overdue': int(overdue),
      'milestones': int(milestones),
      'logged_hours': str(hours),
      'source': 'persistent enterprise work-items, not approved scheduling baselines',
    }
