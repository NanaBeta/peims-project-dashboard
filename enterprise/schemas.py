from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class ProjectOut(ModelOut):
    id: str
    title: str
    currency: str
    role: str

class ActivityOut(ModelOut):
    id: str
    external_id: str
    title: str
    actual_pct: Decimal
    version: int

class ActivityCreate(BaseModel):
    external_id: str = Field(min_length=1,max_length=64)
    title: str = Field(min_length=1,max_length=200)
    actual_pct: Decimal = Field(default=0,ge=0,le=100,max_digits=5,decimal_places=2)

class ProgressUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    actual_pct: Decimal = Field(ge=0,le=100, max_digits=5, decimal_places=2)

class RFIOut(ModelOut):
    id: str
    reference: str
    subject: str
    status: str
    version: int

class RFICreate(BaseModel):
    reference: str = Field(min_length=1,max_length=64)
    subject: str = Field(min_length=1,max_length=300)

class RFIUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    status: Literal['open','in_review','answered','closed']

class CostOut(ModelOut):
    id: str
    description: str
    category: str
    amount: Decimal
    version: int

class CostCreate(BaseModel):
    description: str = Field(min_length=1,max_length=300)
    category: Literal['budget','actual','commitment']
    amount: Decimal = Field(ge=0,max_digits=18,decimal_places=2)

class CostUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    amount: Decimal = Field(ge=0,max_digits=18,decimal_places=2)

class AuditOut(ModelOut):
    id: str
    actor_sub: str
    event_type: str
    entity_id: str
    changed_fields: list[str]
    happened_at: str | None = None

# v0.5 workspace / membership schemas
from datetime import date

Role = Literal['viewer', 'engineer', 'manager']
ActionPriority = Literal['low', 'medium', 'high', 'critical']
ActionStatus = Literal['open', 'in_progress', 'blocked', 'done']
DocumentStatus = Literal['draft', 'in_review', 'approved', 'superseded']

class MemberOut(ModelOut):
    principal_sub: str
    role: Role
    version: int

class MemberCreate(BaseModel):
    principal_sub: str = Field(min_length=1, max_length=255)
    role: Role

class MemberEdit(BaseModel):
    expected_version: int = Field(ge=1)
    role: Role

class ActionOut(ModelOut):
    id: str
    reference: str
    summary: str
    assigned_sub: str | None
    due_date: date | None
    priority: ActionPriority
    status: ActionStatus
    version: int

class ActionCreate(BaseModel):
    reference: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=300)
    assigned_sub: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    priority: ActionPriority = 'medium'

class ActionEdit(BaseModel):
    expected_version: int = Field(ge=1)
    status: ActionStatus
    priority: ActionPriority
    assigned_sub: str | None = Field(default=None, max_length=255)
    due_date: date | None = None

class DocumentOut(ModelOut):
    id: str
    reference: str
    title: str
    revision: str
    status: DocumentStatus
    version: int

class DocumentCreate(BaseModel):
    reference: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=300)
    revision: str = Field(default='A', min_length=1, max_length=32)

class DocumentEdit(BaseModel):
    expected_version: int = Field(ge=1)
    revision: str = Field(min_length=1, max_length=32)
    status: DocumentStatus
