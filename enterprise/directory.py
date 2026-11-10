"""v0.6.3: authenticated organization directory, never exposed to the public demo.

Project-local spreadsheet suggestions remain in smart_entry.py. Shared entries are
manually submitted and approved, then available only where a project manager
explicitly enables the directory and user belongs to the same organization.
"""
from __future__ import annotations

from uuid import uuid4
from unicodedata import normalize
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise.auth import Identity, get_identity
from enterprise.database import get_db
from enterprise.models import (
    Organization, OrganizationMember, DirectoryEntry, OrganizationAuditEvent, Project,
)
from enterprise.permissions import membership, audited

router = APIRouter(prefix='/v1', tags=['organization-directory'])

DirectoryKind = Literal['contractor','supplier','discipline','person','category','document_type']
DirectoryStatus = Literal['pending','approved','rejected','archived']

class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)

class OrgOut(BaseModel):
    id: str
    name: str
    role: Literal['admin','member']

class OrgMemberAdd(BaseModel):
    principal_sub: str = Field(min_length=1,max_length=255)
    role: Literal['admin','member'] = 'member'

class OrgMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    principal_sub: str
    role: Literal['admin','member']

class EntryCreate(BaseModel):
    kind: DirectoryKind
    value: str = Field(min_length=1, max_length=160)

class EntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: DirectoryKind
    value: str
    status: DirectoryStatus
    version: int

class Review(BaseModel):
    expected_version: int = Field(ge=1)
    decision: Literal['approved','rejected','archived']

class LinkOrganization(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)

class DirectorySettingsEdit(BaseModel):
    expected_version: int = Field(ge=1)
    enabled: bool

class DirectorySettingsOut(BaseModel):
    organization_id: str | None
    enabled: bool
    version: int

class SuggestionOut(BaseModel):
    mode: Literal['project_only','hybrid']
    kind: DirectoryKind
    approved_values: list[str]


def cleaned_value(text: str, what: str, maximum: int) -> str:
    val = ' '.join(normalize('NFKC', text).strip().split())
    if not val or len(val) > maximum or any(ord(c)<32 or ord(c)==127 for c in val):
        raise HTTPException(status_code=422,detail=f'Invalid {what}')
    if val[0] in ('=', '+', '-', '@'):
        raise HTTPException(status_code=422,detail=f'Invalid {what}')
    return val


def org_membership(db: Session, org_id: str, identity: Identity, *, admin: bool = False) -> OrganizationMember:
    row = db.scalar(select(OrganizationMember).where(
        OrganizationMember.organization_id==org_id,
        OrganizationMember.principal_sub==identity.sub,
    ).execution_options(populate_existing=True))
    if row is None:
        # Non-members learn nothing about org existence or approval records.
        raise HTTPException(status_code=404,detail='Organization not found')
    if admin and row.role != 'admin':
        raise HTTPException(status_code=403,detail='Organization admin role required')
    return row


def org_audit(db: Session, org_id: str, actor: str, event: str, target: str, fields: list[str]) -> None:
    db.add(OrganizationAuditEvent(id=str(uuid4()),organization_id=org_id,
                                  actor_sub=actor,event_type=event,entity_id=target,
                                  changed_fields=fields))


@router.post('/organizations',response_model=OrgOut,status_code=201)
def create_organization(payload: OrgCreate, identity: Identity=Depends(get_identity),
                        db: Session=Depends(get_db)):
    # Fail closed: tenant creation is a privileged provisioning operation.
    authorized={x.strip() for x in os.environ.get('PEIMS_ORG_BOOTSTRAP_SUBS','').split(',') if x.strip()}
    if identity.sub not in authorized:
        raise HTTPException(status_code=403,detail='Organization provisioning not permitted')
    name=cleaned_value(payload.name,'organization name',160)
    org=Organization(id=str(uuid4()),name=name)
    db.add(org)
    db.add(OrganizationMember(organization_id=org.id,principal_sub=identity.sub,role='admin'))
    org_audit(db,org.id,identity.sub,'organization.created',org.id,['name'])
    db.commit()
    return OrgOut(id=org.id,name=org.name,role='admin')


@router.get('/organizations',response_model=list[OrgOut])
def my_organizations(identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    rows=db.execute(select(Organization,OrganizationMember.role)
                    .join(OrganizationMember,OrganizationMember.organization_id==Organization.id)
                    .where(OrganizationMember.principal_sub==identity.sub)
                    .order_by(Organization.name,Organization.id)).all()
    return [OrgOut(id=o.id,name=o.name,role=role) for o,role in rows]


@router.get('/organizations/{organization_id}/members',response_model=list[OrgMemberOut])
def list_organization_members(organization_id: str, identity: Identity=Depends(get_identity),
                              db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity,admin=True)
    return list(db.scalars(select(OrganizationMember)
                    .where(OrganizationMember.organization_id==organization_id)
                    .order_by(OrganizationMember.principal_sub)))


@router.post('/organizations/{organization_id}/members',status_code=201,response_model=OrgMemberOut)
def add_organization_member(organization_id: str,payload: OrgMemberAdd,
                             identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity,admin=True)
    sub=cleaned_value(payload.principal_sub,'principal',255)
    row=OrganizationMember(organization_id=organization_id,principal_sub=sub,role=payload.role)
    db.add(row)
    org_audit(db,organization_id,identity.sub,'organization.member_added',sub,['role'])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,detail='Organization membership already exists') from None
    return row


@router.delete('/organizations/{organization_id}/members/{principal_sub}',status_code=204)
def revoke_organization_member(organization_id: str,principal_sub: str,
                                identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity,admin=True)
    if principal_sub==identity.sub:
        raise HTTPException(status_code=403,detail='Cannot revoke your own admin membership')
    member=db.scalar(select(OrganizationMember).where(
        OrganizationMember.organization_id==organization_id,
        OrganizationMember.principal_sub==principal_sub).with_for_update())
    if member is None:
        raise HTTPException(status_code=404,detail='Member not found')
    db.delete(member)
    org_audit(db,organization_id,identity.sub,'organization.member_revoked',principal_sub,['membership'])
    db.commit()
    return None


@router.post('/projects/{project_id}/organization-link',response_model=DirectorySettingsOut)
def link_project(project_id: str,payload: LinkOrganization,identity: Identity=Depends(get_identity),
                 db: Session=Depends(get_db)):
    # Both approvals are mandatory: manager OF project + admin OF target organization.
    membership(db,project_id,identity,finance=True)
    org_membership(db,payload.organization_id,identity,admin=True)
    project=db.scalar(select(Project).where(Project.id==project_id).with_for_update())
    if project is None:
        raise HTTPException(status_code=404,detail='Project not found')
    if project.organization_id not in (None,payload.organization_id):
        raise HTTPException(status_code=409,detail='Project is already linked to an organization')
    if project.organization_id is None:
        project.organization_id=payload.organization_id
        project.directory_enabled=False  # explicit secondary step to opt in
        project.directory_version+=1
        audited(db,project_id,identity.sub,'project.organization_linked',project_id,['organization_id'])
        org_audit(db,payload.organization_id,identity.sub,'project.linked',project_id,['organization_id'])
        db.commit()
    return DirectorySettingsOut(organization_id=project.organization_id,
                                enabled=bool(project.directory_enabled),version=project.directory_version)


@router.get('/projects/{project_id}/directory-settings',response_model=DirectorySettingsOut)
def directory_settings(project_id: str,identity: Identity=Depends(get_identity),
                       db: Session=Depends(get_db)):
    membership(db,project_id,identity)
    p=db.get(Project,project_id)
    return DirectorySettingsOut(organization_id=p.organization_id,enabled=bool(p.directory_enabled),
                                version=p.directory_version)


@router.patch('/projects/{project_id}/directory-settings',response_model=DirectorySettingsOut)
def update_directory_settings(project_id: str,payload: DirectorySettingsEdit,
                               identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    membership(db,project_id,identity,finance=True)
    p=db.scalar(select(Project).where(Project.id==project_id).with_for_update())
    if p.directory_version!=payload.expected_version:
        raise HTTPException(status_code=409,detail='Version conflict: reload directory settings')
    if payload.enabled:
        if p.organization_id is None:
            raise HTTPException(status_code=409,detail='Link an organization before enabling shared suggestions')
        org_membership(db,p.organization_id,identity) # only a member of this org can opt in
    if p.directory_enabled!=payload.enabled:
        p.directory_enabled=payload.enabled
        p.directory_version+=1
        audited(db,project_id,identity.sub,'project.directory_settings_changed',project_id,['directory_enabled'])
        if p.organization_id:
            org_audit(db,p.organization_id,identity.sub,'project.directory_settings_changed',project_id,['directory_enabled'])
        db.commit()
    return DirectorySettingsOut(organization_id=p.organization_id,
                                enabled=bool(p.directory_enabled),version=p.directory_version)


@router.post('/organizations/{organization_id}/directory',response_model=EntryOut,status_code=201)
def propose_entry(organization_id: str,payload: EntryCreate,
                  identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity)
    value=cleaned_value(payload.value,'directory value',160)
    row=DirectoryEntry(id=str(uuid4()),organization_id=organization_id,kind=payload.kind,
                       value=value,normalized_value=value.casefold(),status='pending',
                       submitted_by=identity.sub,version=1)
    db.add(row)
    org_audit(db,organization_id,identity.sub,'directory.proposed',row.id,['kind','value'])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409,detail='This directory value is already registered') from None
    return row


@router.get('/organizations/{organization_id}/directory',response_model=list[EntryOut])
def list_directory(organization_id: str,status: DirectoryStatus=Query(default='pending'),
                   limit: int=Query(default=100,ge=1,le=200),
                   identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity,admin=True)
    return list(db.scalars(select(DirectoryEntry).where(
        DirectoryEntry.organization_id==organization_id,DirectoryEntry.status==status)
        .order_by(DirectoryEntry.kind,DirectoryEntry.value).limit(limit)))


@router.patch('/organizations/{organization_id}/directory/{entry_id}',response_model=EntryOut)
def review_entry(organization_id: str,entry_id: str,payload: Review,
                 identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity,admin=True)
    row=db.scalar(select(DirectoryEntry).where(DirectoryEntry.organization_id==organization_id,
                                                DirectoryEntry.id==entry_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404,detail='Directory entry not found')
    if row.version!=payload.expected_version:
        raise HTTPException(status_code=409,detail='Version conflict: reload directory entry')
    allowed={
        'pending':{'approved','rejected'},
        'approved':{'archived'},
        'archived':{'approved'},
        'rejected':{'approved'},  # admin may reinstate a previously rejected proposal
    }
    if payload.decision not in allowed[row.status]:
        raise HTTPException(status_code=409,detail='Invalid directory review transition')
    row.status=payload.decision
    row.reviewed_by=identity.sub
    row.version+=1
    org_audit(db,organization_id,identity.sub,f'directory.{payload.decision}',row.id,['status'])
    db.commit()
    return row


@router.get('/projects/{project_id}/directory-suggestions',response_model=SuggestionOut)
def shared_suggestions(project_id: str, kind: DirectoryKind,
                       identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    membership(db,project_id,identity)
    project=db.get(Project,project_id)
    if not project.directory_enabled or not project.organization_id:
        return SuggestionOut(mode='project_only',kind=kind,approved_values=[])
    org_membership(db,project.organization_id,identity) # also requires org membership
    values=list(db.scalars(select(DirectoryEntry.value).where(
        DirectoryEntry.organization_id==project.organization_id,
        DirectoryEntry.kind==kind,
        DirectoryEntry.status=='approved')
        .order_by(DirectoryEntry.value).limit(100)))
    return SuggestionOut(mode='hybrid',kind=kind,approved_values=values)


@router.get('/organizations/{organization_id}/directory-audit')
def directory_audit(organization_id: str,
                    identity: Identity=Depends(get_identity),db: Session=Depends(get_db)):
    org_membership(db,organization_id,identity,admin=True)
    events=list(db.scalars(select(OrganizationAuditEvent).where(
        OrganizationAuditEvent.organization_id==organization_id)
        .order_by(OrganizationAuditEvent.happened_at.desc(),OrganizationAuditEvent.id.desc()).limit(100)))
    return [{'id':e.id,'event_type':e.event_type,'actor_sub':e.actor_sub,
             'entity_id':e.entity_id,'changed_fields':e.changed_fields,
             'happened_at':e.happened_at.isoformat()} for e in events]
