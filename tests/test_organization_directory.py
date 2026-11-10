"""Security regression tests: approved only, explicit opt-in, two memberships."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from enterprise.main import app
from enterprise.auth import Identity, get_identity
from enterprise.database import get_db
from enterprise.models import (Base, Project, Member, DirectoryEntry,
                               Organization, OrganizationMember, OrganizationAuditEvent, AuditEvent)


@pytest.fixture
def org_service(monkeypatch):
    monkeypatch.setenv('PEIMS_ORG_BOOTSTRAP_SUBS','alice,charlie')
    engine=create_engine('sqlite+pysqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Project(id='P-A',title='Fictional Project A'),
                    Project(id='P-B',title='Fictional Project B'),
                    Project(id='P-C',title='Fictional Project C')])
        db.add_all([
            Member(project_id='P-A',principal_sub='alice',role='manager'),
            Member(project_id='P-A',principal_sub='bob',role='engineer'),
            Member(project_id='P-A',principal_sub='eve',role='viewer'),
            Member(project_id='P-B',principal_sub='charlie',role='manager'),
            Member(project_id='P-C',principal_sub='alice',role='manager'),
            Member(project_id='P-C',principal_sub='mallory',role='viewer'),
        ])
        db.commit()
    def get_session():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db]=get_session
    app.dependency_overrides[get_identity]=lambda:Identity('alice')
    try:
        with TestClient(app) as client:
            def login(sub):
                app.dependency_overrides[get_identity]=lambda:Identity(sub)
            yield client,engine,login
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_org(client,name):
    r=client.post('/v1/organizations',json={'name':name})
    assert r.status_code==201,r.text
    return r.json()['id']


def propose(client,org,kind='discipline',value='Electrical'):
    r=client.post(f'/v1/organizations/{org}/directory',json={'kind':kind,'value':value})
    assert r.status_code==201,r.text
    return r.json()


def review(client,org,entry,status):
    r=client.patch(f'/v1/organizations/{org}/directory/{entry["id"]}',
                   json={'expected_version':entry['version'],'decision':status})
    assert r.status_code==200,r.text
    return r.json()


def link_and_enable(client,project,org):
    r=client.post(f'/v1/projects/{project}/organization-link',json={'organization_id':org})
    assert r.status_code==200,r.text
    assert r.json()['enabled'] is False
    version=r.json()['version']
    r=client.patch(f'/v1/projects/{project}/directory-settings',
                   json={'enabled':True,'expected_version':version})
    assert r.status_code==200,r.text
    return r.json()['version']


def suggestions(client,project='P-A',kind='discipline'):
    return client.get(f'/v1/projects/{project}/directory-suggestions',params={'kind':kind})


def test_default_project_only_legacy_project_and_authorized_link(org_service):
    client,engine,login=org_service
    initial=suggestions(client).json()
    assert initial=={'mode':'project_only','kind':'discipline','approved_values':[]}
    assert client.patch('/v1/projects/P-A/directory-settings',json={'enabled':True,'expected_version':1}).status_code==409
    org=create_org(client,'Example Organization')
    login('bob')
    assert client.post('/v1/projects/P-A/organization-link',json={'organization_id':org}).status_code==403
    login('charlie')
    assert client.post('/v1/projects/P-B/organization-link',json={'organization_id':org}).status_code==404
    login('alice')
    linked=client.post('/v1/projects/P-A/organization-link',json={'organization_id':org})
    assert linked.status_code==200 and linked.json()['enabled'] is False
    assert suggestions(client).json()['mode']=='project_only'
    assert client.patch('/v1/projects/P-A/directory-settings',
                        json={'enabled':True,'expected_version':linked.json()['version']}).status_code==200
    with Session(engine) as db:
        p=db.get(Project,'P-A')
        assert p.organization_id==org and p.directory_enabled
        assert db.get(Project,'P-B').organization_id is None
        assert any(e.event_type=='project.organization_linked' for e in db.scalars(select(AuditEvent)))


def test_only_approved_values_and_no_automatic_promotion(org_service):
    client,engine,login=org_service
    org=create_org(client,'Factory Operations')
    link_and_enable(client,'P-A',org)
    pending=propose(client,org,'supplier','ABC Services')
    assert pending['status']=='pending'
    assert suggestions(client,kind='supplier').json()['approved_values']==[]
    review(client,org,pending,'approved')
    assert suggestions(client,kind='supplier').json()=={
        'mode':'hybrid','kind':'supplier','approved_values':['ABC Services']}
    # Existing project data is not copied into org directory or published automatically.
    with Session(engine) as db:
        assert len(list(db.scalars(select(DirectoryEntry))))==1
        assert any(e.event_type=='directory.approved' for e in db.scalars(select(OrganizationAuditEvent)))
    other=propose(client,org,'discipline','Electrical')
    assert suggestions(client,kind='discipline').json()['approved_values']==[]
    review(client,org,other,'rejected')
    assert suggestions(client,kind='discipline').json()['approved_values']==[]


def test_cross_tenant_and_cross_project_access_masked(org_service):
    client,_,login=org_service
    org1=create_org(client,'Organization One')
    link_and_enable(client,'P-A',org1)
    a=review(client,org1,propose(client,org1,value='Electrical'),'approved')
    # Alice is a P-C manager, but that project has not opted in to org directory.
    assert suggestions(client,'P-C').json()['mode']=='project_only'
    login('charlie')
    org2=create_org(client,'Organization Two')
    link_and_enable(client,'P-B',org2)
    review(client,org2,propose(client,org2,value='Mechanical'),'approved')
    assert suggestions(client,'P-B').json()['approved_values']==['Mechanical']
    assert suggestions(client,'P-A').status_code==404
    assert client.get(f'/v1/organizations/{org1}/directory').status_code==404
    assert client.patch(f'/v1/organizations/{org1}/directory/{a["id"]}',
                        json={'expected_version':a['version'],'decision':'archived'}).status_code==404
    login('alice')
    assert suggestions(client,'P-A').json()['approved_values']==['Electrical']
    assert client.get(f'/v1/organizations/{org2}/directory').status_code==404
    assert client.post('/v1/projects/P-A/organization-link',json={'organization_id':org2}).status_code==404


def test_project_membership_alone_cannot_read_org_directory(org_service):
    client,_,login=org_service
    org=create_org(client,'Machine Shop')
    link_and_enable(client,'P-A',org)
    review(client,org,propose(client,org,'contractor','Power Team'),'approved')
    login('bob')
    assert suggestions(client,kind='contractor').status_code==404
    assert client.get(f'/v1/organizations/{org}/directory').status_code==404
    login('alice')
    added=client.post(f'/v1/organizations/{org}/members',json={'principal_sub':'bob','role':'member'})
    assert added.status_code==201
    login('bob')
    assert suggestions(client,kind='contractor').json()['approved_values']==['Power Team']
    # Members may suggest but can't review or see the approval queue.
    proposed=propose(client,org,'discipline','Instrumentation')
    assert client.patch(f'/v1/organizations/{org}/directory/{proposed["id"]}',
                        json={'expected_version':1,'decision':'approved'}).status_code==403
    assert client.get(f'/v1/organizations/{org}/directory').status_code==403
    login('eve')
    assert suggestions(client,kind='contractor').status_code==404
    login('alice')
    assert client.delete(f'/v1/organizations/{org}/members/bob').status_code==204
    login('bob')
    assert suggestions(client,kind='contractor').status_code==404


def test_approvals_version_conflicts_duplicates_and_archive(org_service):
    client,_,login=org_service
    org=create_org(client,'Example Operations')
    link_and_enable(client,'P-A',org)
    item=propose(client,org,'supplier','  ABC   SERVICES  ')
    assert item['value']=='ABC SERVICES'
    assert client.post(f'/v1/organizations/{org}/directory',
                       json={'kind':'supplier','value':'abc services'}).status_code==409
    assert client.post(f'/v1/organizations/{org}/directory',
                       json={'kind':'supplier','value':'=HYPERLINK("URL","bad")'}).status_code==422
    assert client.post(f'/v1/organizations/{org}/directory',
                       json={'kind':'not_a_kind','value':'Value'}).status_code==422
    approved=review(client,org,item,'approved')
    assert client.patch(f'/v1/organizations/{org}/directory/{item["id"]}',
                        json={'expected_version':1,'decision':'archived'}).status_code==409
    assert suggestions(client,kind='supplier').json()['approved_values']==['ABC SERVICES']
    archived=review(client,org,approved,'archived')
    assert suggestions(client,kind='supplier').json()['approved_values']==[]
    review(client,org,archived,'approved')
    assert suggestions(client,kind='supplier').json()['approved_values']==['ABC SERVICES']
    assert client.delete(f'/v1/organizations/{org}/members/alice').status_code==403


def test_toggle_opt_in_and_disabled_visibility(org_service):
    client,_,login=org_service
    org=create_org(client,'Enterprise')
    link_and_enable(client,'P-A',org)
    review(client,org,propose(client,org,'discipline','Electrical'),'approved')
    settings=client.get('/v1/projects/P-A/directory-settings').json()
    assert client.patch('/v1/projects/P-A/directory-settings',
                        json={'enabled':False,'expected_version':settings['version']-1}).status_code==409
    disabled=client.patch('/v1/projects/P-A/directory-settings',
                         json={'enabled':False,'expected_version':settings['version']})
    assert disabled.status_code==200
    assert suggestions(client).json()=={'mode':'project_only','kind':'discipline','approved_values':[]}
    assert client.patch('/v1/projects/P-A/directory-settings',
                        json={'enabled':True,'expected_version':settings['version']}).status_code==409
    login('bob')
    assert client.patch('/v1/projects/P-A/directory-settings',
                        json={'enabled':True,'expected_version':disabled.json()['version']}).status_code==403
    login('alice')
    assert client.patch('/v1/projects/P-A/directory-settings',
                        json={'enabled':True,'expected_version':disabled.json()['version']}).status_code==200
    assert suggestions(client).json()['approved_values']==['Electrical']


def test_org_creation_invalid_fields_and_auth(org_service):
    client,_,login=org_service
    assert client.post('/v1/organizations',json={'name':'  '}).status_code==422
    org=create_org(client,'Example Org')
    login('eve')
    assert client.post('/v1/organizations',json={'name':'Unauthorized Organization'}).status_code==403
    assert client.get('/v1/organizations').json()==[]
    assert client.get(f'/v1/organizations/{org}/members').status_code==404
    assert client.post(f'/v1/organizations/{org}/directory',json={'kind':'supplier','value':'A'}).status_code==404
    app.dependency_overrides.pop(get_identity)
    assert client.get('/v1/organizations').status_code==401
    assert client.get('/v1/projects/P-A/directory-suggestions?kind=discipline').status_code==401
