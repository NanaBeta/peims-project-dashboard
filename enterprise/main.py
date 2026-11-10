"""PEIMS v0.4 enterprise API prototype, separate from the public Streamlit demo.
Requires a managed PostgreSQL database, an OIDC identity provider and explicit
membership provisioning before use. Never exposed automatically by Streamlit.
"""
from __future__ import annotations
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from enterprise.database import get_db, session_factory
from enterprise.auth import Identity, get_identity
from enterprise.models import Project, Member, Activity, RFI, CostLine, AuditEvent
from enterprise.permissions import membership, audited
from enterprise.workspace import router as workspace_router
from enterprise.directory import router as directory_router
from enterprise.work_management import router as work_management_router
from sqlalchemy import text
from enterprise.schemas import ProjectOut, ActivityOut, ActivityCreate, ProgressUpdate, RFIOut, RFICreate, RFIUpdate, CostOut, CostCreate, CostUpdate

app = FastAPI(title='PEIMS enterprise API (staging foundation)', version='0.8.0', docs_url=None, redoc_url=None)

@app.get('/healthz')
def healthz():
    return {'status':'up', 'service':'peims-api', 'note':'Liveness only; not proof of DB readiness'}


@app.get('/v1/projects', response_model=list[ProjectOut])
def list_projects(identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    rows = db.execute(select(Project, Member.role).join(Member, Member.project_id==Project.id)
                      .where(Member.principal_sub == identity.sub).order_by(Project.id)).all()
    return [ProjectOut(id=p.id,title=p.title,currency=p.currency,role=role) for p,role in rows]

@app.get('/v1/projects/{project_id}/activities', response_model=list[ActivityOut])
def list_activities(project_id:str, identity: Identity=Depends(get_identity), db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    return list(db.scalars(select(Activity).where(Activity.project_id==project_id).order_by(Activity.external_id)))

@app.post('/v1/projects/{project_id}/activities',response_model=ActivityOut,status_code=201)
def create_activity(project_id:str,payload:ActivityCreate,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    external_id,title=payload.external_id.strip(),payload.title.strip()
    if not external_id or not title:raise HTTPException(status_code=422,detail='Blank fields not permitted')
    row=Activity(id=str(uuid4()),project_id=project_id,external_id=external_id,
                 title=title,actual_pct=payload.actual_pct,version=1)
    db.add(row);audited(db,project_id,identity.sub,'activity.created',row.id,['external_id','title','actual_pct'])
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(status_code=409,detail='Activity external ID already exists')
    db.refresh(row)
    return row

@app.put('/v1/projects/{project_id}/activities/{activity_id}', response_model=ActivityOut)
def update_activity(project_id:str, activity_id:str, payload:ProgressUpdate,
                    identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    row = db.scalar(select(Activity).where(Activity.id==activity_id,Activity.project_id==project_id).with_for_update())
    if row is None: raise HTTPException(status_code=404,detail='Activity not found')
    if row.version != payload.expected_version: raise HTTPException(status_code=409,detail='Version conflict: reload record')
    row.actual_pct = payload.actual_pct
    row.version += 1
    audited(db,project_id,identity.sub,'activity.progress_updated',row.id,['actual_pct'])
    db.commit();db.refresh(row)
    return row

@app.get('/v1/projects/{project_id}/rfis',response_model=list[RFIOut])
def list_rfis(project_id:str, identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity)
    return list(db.scalars(select(RFI).where(RFI.project_id==project_id).order_by(RFI.reference)))

@app.post('/v1/projects/{project_id}/rfis', response_model=RFIOut, status_code=201)
def create_rfi(project_id:str, payload:RFICreate,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    reference,subject = payload.reference.strip(),payload.subject.strip()
    if not (reference and subject): raise HTTPException(status_code=422, detail='Blank fields not permitted')
    row=RFI(id=str(uuid4()),project_id=project_id,reference=reference,subject=subject,status='open')
    db.add(row); audited(db,project_id,identity.sub,'rfi.created',row.id,['reference','subject','status'])
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(status_code=409,detail='RFI reference already exists')
    db.refresh(row)
    return row

@app.patch('/v1/projects/{project_id}/rfis/{rfi_id}', response_model=RFIOut)
def update_rfi(project_id:str,rfi_id:str,payload:RFIUpdate,
               identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,writable=True)
    row=db.scalar(select(RFI).where(RFI.id==rfi_id,RFI.project_id==project_id).with_for_update())
    if row is None: raise HTTPException(status_code=404,detail='RFI not found')
    if row.version != payload.expected_version: raise HTTPException(status_code=409,detail='Version conflict: reload record')
    row.status=payload.status;row.version+=1
    audited(db,project_id,identity.sub,'rfi.status_changed',row.id,['status'])
    db.commit();db.refresh(row)
    return row

@app.get('/v1/projects/{project_id}/cost-lines', response_model=list[CostOut])
def list_costs(project_id:str,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,finance=True)
    return list(db.scalars(select(CostLine).where(CostLine.project_id==project_id).order_by(CostLine.id)))

@app.post('/v1/projects/{project_id}/cost-lines',response_model=CostOut,status_code=201)
def add_cost(project_id:str,payload:CostCreate,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,finance=True)
    name=payload.description.strip()
    if not name: raise HTTPException(status_code=422,detail='Blank description')
    row=CostLine(id=str(uuid4()),project_id=project_id,description=name,
                 category=payload.category,amount=payload.amount)
    db.add(row);audited(db,project_id,identity.sub,'cost.created',row.id,['category','amount','description'])
    db.commit();db.refresh(row)
    return row

@app.patch('/v1/projects/{project_id}/cost-lines/{line_id}',response_model=CostOut)
def edit_cost(project_id:str,line_id:str,payload:CostUpdate,identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,finance=True)
    row=db.scalar(select(CostLine).where(CostLine.id==line_id,CostLine.project_id==project_id).with_for_update())
    if row is None:raise HTTPException(status_code=404,detail='Cost line not found')
    if row.version != payload.expected_version:raise HTTPException(status_code=409,detail='Version conflict: reload record')
    row.amount=payload.amount;row.version+=1
    audited(db,project_id,identity.sub,'cost.amount_updated',row.id,['amount'])
    db.commit();db.refresh(row)
    return row

@app.get('/v1/projects/{project_id}/audit')
def audit_events(project_id:str, identity:Identity=Depends(get_identity),db:Session=Depends(get_db)):
    membership(db,project_id,identity,finance=True)
    events=list(db.scalars(select(AuditEvent).where(AuditEvent.project_id==project_id)
                           .order_by(AuditEvent.happened_at.desc(),AuditEvent.id.desc()).limit(100)))
    return [{'id':e.id,'actor_sub':e.actor_sub,'event_type':e.event_type,
             'entity_id':e.entity_id,'changed_fields':e.changed_fields,
             'happened_at':e.happened_at.isoformat()} for e in events]


@app.get('/readyz')
def readyz():
    """Staging database readiness without exposing credentials or service details."""
    try:
        with session_factory()() as db:
            db.execute(text('SELECT 1'))
        return {'status': 'ready'}
    except Exception:
        raise HTTPException(status_code=503, detail='Database not ready') from None


app.include_router(workspace_router)
app.include_router(directory_router)

app.include_router(work_management_router)
