"""API authorization/integrity tests using ephemeral SQLite test DB (never production)."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from enterprise.main import app
from enterprise.auth import get_identity, Identity, verify_access_token
from enterprise.database import get_db
from enterprise.models import Base, Project, Member, Activity, RFI, CostLine, AuditEvent

@pytest.fixture()
def service():
    engine=create_engine('sqlite+pysqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([Project(id='P1',title='Fictional Project One',currency='GHS'),
                   Project(id='P2',title='Fictional Project Two',currency='GHS')])
        s.add_all([Member(project_id='P1',principal_sub='engineer-1',role='engineer'),
                   Member(project_id='P1',principal_sub='manager-1',role='manager'),
                   Member(project_id='P1',principal_sub='viewer-1',role='viewer'),
                   Member(project_id='P2',principal_sub='manager-2',role='manager')])
        s.add(Activity(id='A1',project_id='P1',external_id='V01',title='Fictional task',actual_pct=25))
        s.commit()
    def session():
        with Session(engine) as s:yield s
    def logged_in():return Identity('engineer-1')
    app.dependency_overrides[get_db]=session
    app.dependency_overrides[get_identity]=logged_in
    try:
        with TestClient(app) as client:
            yield client,engine,logged_in
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

def test_membership_filters_project_lists_and_cross_project_read(service):
    client,_,logged_in=service
    out=client.get('/v1/projects')
    assert out.status_code==200
    assert [row['id'] for row in out.json()]==['P1']
    assert client.get('/v1/projects/P2/rfis').status_code==404
    assert client.get('/v1/projects/P2/audit').status_code==404

def test_viewer_cannot_write_or_read_audit(service):
    client,_,logged_in=service
    app.dependency_overrides[get_identity]=lambda: Identity('viewer-1')
    assert client.get('/v1/projects/P1/activities').status_code==200
    assert client.put('/v1/projects/P1/activities/A1',json={'actual_pct':60,'expected_version':1}).status_code==403
    assert client.post('/v1/projects/P1/cost-lines',json={'description':'line','category':'actual','amount':'50'}).status_code==403
    assert client.get('/v1/projects/P1/audit').status_code==403
    assert client.get('/v1/projects/P1/cost-lines').status_code==403

def test_version_conflict_and_audit_atomic(service):
    client,engine,_=service
    path='/v1/projects/P1/activities/A1'
    assert client.put(path,json={'actual_pct':35,'expected_version':1}).status_code==200
    bad=client.put(path,json={'actual_pct':50,'expected_version':1})
    assert bad.status_code==409
    assert client.put(path,json={'actual_pct':105,'expected_version':2}).status_code==422
    with Session(engine) as s:
        a=s.get(Activity,'A1');assert float(a.actual_pct)==35 and a.version==2
        audit=list(s.scalars(select(AuditEvent)));assert len(audit)==1
        assert audit[0].actor_sub=='engineer-1' and audit[0].changed_fields==['actual_pct']

def test_rfi_creation_edit_uniqueness_and_finance_permissions(service):
    client,_,_=service
    base='/v1/projects/P1'
    rf=client.post(base+'/rfis',json={'reference':'RFI-1','subject':'Fan connection clearance'})
    assert rf.status_code==201,rf.text
    assert client.post(base+'/rfis',json={'reference':'RFI-1','subject':'Duplicate'}).status_code==409
    r=client.patch(base+'/rfis/'+rf.json()['id'],json={'expected_version':1,'status':'answered'})
    assert r.status_code==200 and r.json()['version']==2
    assert client.post(base+'/cost-lines',json={'description':'Materials','category':'budget','amount':'100'}).status_code==403
    app.dependency_overrides[get_identity]=lambda:Identity('manager-1')
    c=client.post(base+'/cost-lines',json={'description':'Materials','category':'actual','amount':'123.45'})
    assert c.status_code==201,c.text
    assert client.get(base+'/audit').status_code==200

def test_anonymous_or_invalid_auth_fails_closed(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.delenv('PEIMS_OIDC_ISSUER',raising=False)
    assert TestClient(app).get('/v1/projects').status_code==401
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ex:verify_access_token('not.a.jwt')
    assert ex.value.status_code==503


def test_create_task_and_update_cost_with_versions(service):
    client,_,_=service
    base='/v1/projects/P1'
    task=client.post(base+'/activities',json={'external_id':'V02','title':'Cable termination','actual_pct':10})
    assert task.status_code==201,task.text
    assert client.post(base+'/activities',json={'external_id':'V02','title':'Duplicate'}).status_code==409
    app.dependency_overrides[get_identity]=lambda:Identity('manager-1')
    new=client.post(base+'/cost-lines',json={'description':'Motor supply','category':'commitment','amount':'150.00'})
    assert new.status_code==201,new.text
    url=base+'/cost-lines/'+new.json()['id']
    updated=client.patch(url,json={'expected_version':1,'amount':'160.00'})
    assert updated.status_code==200,updated.text
    assert float(updated.json()['amount'])==160
    assert client.patch(url,json={'expected_version':1,'amount':'170.00'}).status_code==409
    assert client.patch(url,json={'expected_version':2,'amount':'-1.00'}).status_code==422


def test_real_rs256_token_claim_validation_with_stub_jwks(monkeypatch):
    import jwt
    from datetime import datetime, timezone, timedelta
    from cryptography.hazmat.primitives.asymmetric import rsa
    from enterprise import auth
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    class StubJwks:
        def get_signing_key_from_jwt(self, token):
            class Key: pass
            k=Key();k.key=private.public_key()
            return k
    monkeypatch.setattr(auth, 'jwks_client',lambda url:StubJwks())
    monkeypatch.setenv('PEIMS_OIDC_ISSUER','https://id.example.test/')
    monkeypatch.setenv('PEIMS_OIDC_JWKS_URL','https://id.example.test/jwks')
    monkeypatch.setenv('PEIMS_OIDC_AUDIENCE','peims-api-test')
    now=datetime.now(timezone.utc)
    claims={'sub':'user:123','iss':'https://id.example.test/','aud':'peims-api-test',
            'iat':now,'exp':now+timedelta(minutes=10)}
    valid=jwt.encode(claims,private,algorithm='RS256')
    assert auth.verify_access_token(valid).sub=='user:123'
    wrong=jwt.encode({**claims,'aud':'other-api'},private,algorithm='RS256')
    with pytest.raises(Exception) as ex: auth.verify_access_token(wrong)
    assert ex.value.status_code==401
    expired=jwt.encode({**claims,'exp':now-timedelta(hours=1)},private,algorithm='RS256')
    with pytest.raises(Exception) as ex: auth.verify_access_token(expired)
    assert ex.value.status_code==401
