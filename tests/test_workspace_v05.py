"""v0.5 app-layer security and persistent-workspace tests (SQLite test substitute).

Production PostgreSQL migrations and OIDC integration require a separate staging test.
"""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from enterprise.database import get_db
from enterprise.auth import get_identity, Identity
from enterprise.main import app
from enterprise.models import Base, Member, Project, ActionItem, DocumentRecord, AuditEvent


@pytest.fixture
def workspace(tmp_path):
    # File-backed DB persists across API request transactions and TestClient restarts.
    url = f"sqlite+pysqlite:///{tmp_path / 'demo.sqlite'}"
    engine = create_engine(url, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([Project(id='P1', title='Fictional Pilot', currency='GHS'),
                   Project(id='P2', title='Foreign Project', currency='GHS'),
                   Member(project_id='P1', principal_sub='manager-1', role='manager'),
                   Member(project_id='P1', principal_sub='engineer-1', role='engineer'),
                   Member(project_id='P1', principal_sub='viewer-1', role='viewer'),
                   Member(project_id='P2', principal_sub='manager-2', role='manager')])
        s.commit()
    def db():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_identity] = lambda: Identity('manager-1')
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(sub):
    app.dependency_overrides[get_identity] = lambda: Identity(sub)


def test_role_management_and_audit(workspace):
    c,engine=workspace
    url='/v1/projects/P1/members'
    out=c.get(url)
    assert out.status_code==200 and len(out.json())==3
    created=c.post(url,json={'principal_sub':'engineer-2','role':'viewer'})
    assert created.status_code==201,created.text
    assert created.json()['version']==1
    assert c.post(url,json={'principal_sub':'engineer-2','role':'viewer'}).status_code==409
    assert c.post(url,json={'principal_sub':'  ','role':'manager'}).status_code==422
    change=c.patch(url+'/engineer-2',json={'expected_version':1,'role':'engineer'})
    assert change.status_code==200 and change.json()['version']==2
    assert c.patch(url+'/engineer-2',json={'expected_version':1,'role':'viewer'}).status_code==409
    assert c.patch(url+'/manager-1',json={'expected_version':1,'role':'viewer'}).status_code==403
    assert c.delete(url+'/manager-1?expected_version=1').status_code==403
    assert c.delete(url+'/engineer-2?expected_version=2').status_code==204
    with Session(engine) as s:
        events=list(s.scalars(select(AuditEvent).where(AuditEvent.project_id=='P1')))
        assert [e.event_type for e in events]==['member.added','member.role_changed','member.revoked']
        assert s.get(Member,('P1','engineer-2')) is None


def test_workspace_persists_and_versions_reject_stale_edits(workspace):
    c,engine=workspace
    base='/v1/projects/P1'
    action=c.post(base+'/action-items',json={'reference':'ACT-01','summary':'Order pump cables',
                                              'assigned_sub':'engineer-1','due_date':'2026-11-20','priority':'high'})
    assert action.status_code==201,action.text
    action_id=action.json()['id']
    assert c.post(base+'/action-items',json={'reference':'ACT-01','summary':'duplicate'}).status_code==409
    assert c.post(base+'/action-items',json={'reference':'ACT-02','summary':'No member',
                'assigned_sub':'someone-else'}).status_code==422
    updated=c.patch(base+'/action-items/'+action_id,json={'expected_version':1,'status':'in_progress',
                'priority':'critical','assigned_sub':'engineer-1','due_date':'2026-11-21'})
    assert updated.status_code==200 and updated.json()['version']==2
    assert c.patch(base+'/action-items/'+action_id,json={'expected_version':1,'status':'done',
                'priority':'low'}).status_code==409
    doc=c.post(base+'/document-records',json={'reference':'DWG-100','title':'Example fan plan','revision':'A'})
    assert doc.status_code==201,doc.text
    doc_id=doc.json()['id']
    assert c.post(base+'/document-records',json={'reference':'DWG-100','title':'duplicate'}).status_code==409
    assert c.patch(base+'/document-records/'+doc_id,json={'expected_version':1,
                'status':'in_review','revision':'B'}).status_code==200
    assert c.patch(base+'/document-records/'+doc_id,json={'expected_version':1,
                'status':'approved','revision':'C'}).status_code==409
    summary=c.get(base+'/workspace-summary')
    assert summary.status_code==200 and summary.json()['actions']=={'in_progress':1}
    assert summary.json()['documents']=={'in_review':1}
    with Session(engine) as s:
        # Verifies data committed to disk and not held in Python session state.
        assert s.get(ActionItem,action_id).priority=='critical'
        assert s.get(DocumentRecord,doc_id).revision=='B'
        events=list(s.scalars(select(AuditEvent).where(AuditEvent.project_id=='P1')))
        assert len(events)==4
    assert c.get(base+'/document-records?limit=0').status_code==422
    assert c.get(base+'/action-items?offset=-1').status_code==422


def test_isolation_and_roles(workspace):
    c,_=workspace
    base='/v1/projects/P1'
    assert c.get('/v1/projects/P2/action-items').status_code==404
    assert c.post('/v1/projects/P2/document-records',json={'reference':'D','title':'X'}).status_code==404
    assert c.get('/v1/projects/P2/members').status_code==404
    login('viewer-1')
    assert c.get(base+'/action-items').status_code==200
    assert c.get(base+'/document-records').status_code==200
    assert c.get(base+'/workspace-summary').status_code==200
    assert c.get(base+'/members').status_code==403
    assert c.post(base+'/action-items',json={'reference':'A','summary':'X'}).status_code==403
    assert c.post(base+'/document-records',json={'reference':'D','title':'X'}).status_code==403
    login('engineer-1')
    assert c.post(base+'/action-items',json={'reference':'ENG-1','summary':'Contractor follow-up'}).status_code==201
    assert c.get(base+'/members').status_code==403
    assert c.post(base+'/members',json={'principal_sub':'intruder','role':'manager'}).status_code==403
    login('viewer-1')
    assert c.patch(base+'/action-items/'+c.get(base+'/action-items').json()[0]['id'],
                   json={'expected_version':1,'status':'done','priority':'high'}).status_code==403
    login('manager-2')
    assert c.get('/v1/projects/P1/document-records').status_code==404


def test_membership_revocation_requires_reassignment(workspace):
    c,_=workspace
    base='/v1/projects/P1'
    c.post(base+'/action-items',json={'reference':'D1','summary':'Assigned task','assigned_sub':'engineer-1'})
    assert c.delete(base+'/members/engineer-1?expected_version=1').status_code==409
    # A manager may remove unassigned members but not their own account.
    assert c.delete(base+'/members/viewer-1?expected_version=1').status_code==204


def test_readiness_and_unconfigured_auth(workspace, monkeypatch):
    c,engine=workspace
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr('enterprise.main.session_factory',lambda:sessionmaker(bind=engine))
    assert c.get('/readyz').status_code==200
    app.dependency_overrides.pop(get_identity)
    assert TestClient(app).get('/v1/projects/P1/workspace-summary').status_code==401


def test_readiness_fails_closed_when_not_configured(workspace, monkeypatch):
    c, _ = workspace
    def failed():
        raise RuntimeError('Not configured')
    monkeypatch.setattr('enterprise.main.session_factory', failed)
    assert c.get('/readyz').status_code == 503
    assert 'not ready' in c.get('/readyz').json()['detail'].lower()
