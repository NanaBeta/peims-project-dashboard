"""PEIMS enterprise SQLAlchemy models. Database migrations are mandatory in deployments."""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint, Integer, DateTime, Numeric, JSON, Index
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

class Member(Base):
    __tablename__ = 'members'
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True)
    principal_sub: Mapped[str] = mapped_column(String(255), primary_key=True)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
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
