"""PEIMS enterprise SQLAlchemy models. Database migrations are mandatory in deployments."""
from __future__ import annotations
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint, ForeignKeyConstraint, Integer, DateTime, Numeric, JSON, Index, Date, Boolean, false
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class Project(Base):
    __tablename__ = 'projects'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default='GHS')
    # Legacy projects are deliberately unlinked; directory access defaults OFF.
    organization_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=True)
    directory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    directory_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default='1')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

class Member(Base):
    __tablename__ = 'members'
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    principal_sub: Mapped[str] = mapped_column(String(255), primary_key=True)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("role IN ('viewer','engineer','manager')", name='member_role'),)

class Activity(Base):
    __tablename__ = 'activities'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    actual_pct: Mapped[Decimal] = mapped_column(Numeric(5,2), nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint('project_id','external_id',name='uq_activity_project_external'),
                      CheckConstraint('actual_pct >= 0 AND actual_pct <= 100',name='activity_progress'))

class RFI(Base):
    __tablename__ = 'rfis'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='open')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (UniqueConstraint('project_id','reference',name='uq_rfi_reference'),
                     CheckConstraint("status IN ('open','in_review','answered','closed')", name='rfi_status'))

class CostLine(Base):
    __tablename__ = 'cost_lines'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18,2), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint("category IN ('budget','actual','commitment')",name='cost_category'),
                      CheckConstraint('amount >= 0',name='cost_nonnegative'))

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    actor_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    changed_fields: Mapped[list] = mapped_column(JSON, nullable=False)
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (Index('ix_audit_project_time', 'project_id', 'happened_at'),)


class ActionItem(Base):
    """Persistent follow-up register. No raw documents or sensitive files."""
    __tablename__ = 'action_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    assigned_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    priority: Mapped[str] = mapped_column(String(12), nullable=False, default='medium')
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='open')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        UniqueConstraint('project_id', 'reference', name='uq_action_project_reference'),
        CheckConstraint("priority IN ('low','medium','high','critical')", name='action_priority'),
        CheckConstraint("status IN ('open','in_progress','blocked','done')", name='action_status'),
        Index('ix_action_project_status', 'project_id', 'status'),
    )

class DocumentRecord(Base):
    """Document metadata only: no actual attachment bytes, CAD or confidential drawings."""
    __tablename__ = 'document_records'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    revision: Mapped[str] = mapped_column(String(32), nullable=False, default='A')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='draft')
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        UniqueConstraint('project_id', 'reference', name='uq_document_project_reference'),
        CheckConstraint("status IN ('draft','in_review','approved','superseded')", name='document_status'),
        Index('ix_document_project_status', 'project_id', 'status'),
    )


class Organization(Base):
    """Isolated tenant. A project is never attached automatically."""
    __tablename__ = 'organizations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class OrganizationMember(Base):
    __tablename__ = 'organization_members'
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey('organizations.id', ondelete='CASCADE'), primary_key=True)
    principal_sub: Mapped[str] = mapped_column(String(255), primary_key=True)
    role: Mapped[str] = mapped_column(String(12), nullable=False, default='member')
    __table_args__ = (CheckConstraint("role IN ('admin','member')", name='organization_member_role'),)


class DirectoryEntry(Base):
    """Only manually approved values can enter a cross-project suggestion result."""
    __tablename__ = 'directory_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    value: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default='pending')
    submitted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (
        UniqueConstraint('organization_id','kind','normalized_value',name='uq_directory_org_kind_value'),
        CheckConstraint("kind IN ('contractor','supplier','discipline','person','category','document_type')",name='directory_kind'),
        CheckConstraint("status IN ('pending','approved','rejected','archived')",name='directory_status'),
        Index('ix_directory_approved_lookup','organization_id','kind','status'),
    )


class OrganizationAuditEvent(Base):
    """Organization changes are audited separately from project-scoped changes."""
    __tablename__ = 'organization_audit_events'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    actor_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    changed_fields: Mapped[list] = mapped_column(JSON, nullable=False)
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (Index('ix_organization_audit_time','organization_id','happened_at'),)


class WorkItem(Base):
    """Durable project task; not the separately approved baseline activity."""
    __tablename__ = 'work_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    reference: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False, default='')
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default='task')
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='todo')
    priority: Mapped[str] = mapped_column(String(12), nullable=False, default='medium')
    assigned_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    estimate_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    progress_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (
        UniqueConstraint('project_id', 'reference', name='uq_work_item_project_reference'),
        UniqueConstraint('project_id', 'id', name='uq_work_item_project_id'),
        ForeignKeyConstraint(['project_id', 'parent_id'], ['work_items.project_id', 'work_items.id'], ondelete='RESTRICT', name='fk_work_item_parent'),
        ForeignKeyConstraint(['project_id', 'assigned_sub'], ['members.project_id', 'members.principal_sub'], ondelete='RESTRICT', name='fk_work_item_assignee'),
        CheckConstraint("kind IN ('task','subtask','milestone')", name='work_item_kind'),
        CheckConstraint("status IN ('todo','in_progress','blocked','done')", name='work_item_status'),
        CheckConstraint("priority IN ('low','medium','high','critical')", name='work_item_priority'),
        CheckConstraint('estimate_hours >= 0', name='work_item_hours_nonnegative'),
        CheckConstraint('progress_pct >= 0 AND progress_pct <= 100', name='work_item_progress_range'),
        CheckConstraint('due_date >= start_date', name='work_item_date_order'),
        CheckConstraint('(kind = \'subtask\' AND parent_id IS NOT NULL) OR (kind <> \'subtask\' AND parent_id IS NULL)', name='work_item_parent_kind'),
        CheckConstraint("(kind <> 'milestone') OR (due_date = start_date AND estimate_hours = 0)", name='work_item_milestone'),
        CheckConstraint("(status <> 'done') OR progress_pct = 100", name='work_item_completed_progress'),
        Index('ix_work_item_project_status', 'project_id', 'status'),
        Index('ix_work_item_project_assignee', 'project_id', 'assigned_sub'),
    )


class WorkDependency(Base):
    """Finish-to-start links; composite FKs prevent cross-project references at DB level."""
    __tablename__ = 'work_dependencies'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    predecessor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    successor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (
        ForeignKeyConstraint(['project_id','predecessor_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_dep_predecessor'),
        ForeignKeyConstraint(['project_id','successor_id'], ['work_items.project_id','work_items.id'], ondelete='RESTRICT', name='fk_work_dep_successor'),
        UniqueConstraint('project_id','predecessor_id','successor_id', name='uq_work_dependency_edge'),
        CheckConstraint('predecessor_id <> successor_id', name='work_dependency_no_self'),
        Index('ix_work_dep_successor', 'project_id','successor_id'),
    )


class WorkTimeEntry(Base):
    """Append-only signed timesheet entry. No billing/invoicing is implied."""
    __tablename__ = 'work_time_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    note: Mapped[str] = mapped_column(String(500), nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (
        ForeignKeyConstraint(['project_id','work_item_id'],['work_items.project_id','work_items.id'], ondelete='RESTRICT',name='fk_work_time_item'),
        CheckConstraint('hours > 0 AND hours <= 24', name='work_time_hours_range'),
        Index('ix_work_time_project_date','project_id','work_date'),
    )


class WorkComment(Base):
    """Append-only task comments, without external file uploads or notifications."""
    __tablename__ = 'work_comments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    author_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    __table_args__ = (
        ForeignKeyConstraint(['project_id','work_item_id'],['work_items.project_id','work_items.id'], ondelete='RESTRICT',name='fk_work_comment_item'),
        Index('ix_work_comment_project_item','project_id','work_item_id','created_at'),
    )


class BrowserSession(Base):
    """Opaque browser session hash only; no OAuth tokens or credentials in DB."""
    __tablename__ = 'browser_sessions'
    sid_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index('ix_browser_sessions_expiry','expires_at'),)
