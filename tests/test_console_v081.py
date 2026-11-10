"""Enterprise console integration tests; OIDC and PostgreSQL are replaced by
fakes/SQLite *only inside tests*. Deployed code has no demo login bypass.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, parse_qs
from hashlib import sha256
import re

import pytest
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from enterprise.main import app
from enterprise.database import get_db
from enterprise.models import Base, Project, Member, BrowserSession, WorkItem, WorkComment, AuditEvent
from enterprise import console


@pytest.fixture
def setup(tmp_path,monkeypatch):
    engine=create_engine(f'sqlite+pysqlite:///{tmp_path/"test_console.db"}',connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def fk_on(conn,_):
        cur=conn.cursor();cur.execute('PRAGMA foreign_keys=ON');cur.close()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([Project(id='P1',title='Electrical Substation Modernization',currency='GHS'),
                    Project(id='P2',title='Separate Customer Project',currency='GHS')]);db.flush()
        db.add_all([Member(project_id='P1',principal_sub='alice',role='manager'),
                    Member(project_id='P1',principal_sub='bob',role='engineer'),
                    Member(project_id='P1',principal_sub='reader',role='viewer'),
                    Member(project_id='P2',principal_sub='eve',role='manager')]);db.commit()
    def get_test_db():
        with Session(engine) as db:yield db
    app.dependency_overrides[get_db]=get_test_db
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    class StubJwks:
        def get_signing_key_from_jwt(self,token):
            class Key:pass
            key=Key();key.key=private.public_key();return key
    monkeypatch.setattr(console,'jwks_client',lambda _:StubJwks())
    env={'PEIMS_CONSOLE_ORIGIN':'https://console.example.test',
         'PEIMS_OIDC_ISSUER':'https://id.example.test/',
         'PEIMS_OIDC_JWKS_URL':'https://id.example.test/jwks',
         'PEIMS_CONSOLE_AUTHORIZE_URL':'https://id.example.test/authorize',
         'PEIMS_CONSOLE_TOKEN_URL':'https://id.example.test/token',
         'PEIMS_CONSOLE_CLIENT_ID':'peims-enterprise-web',
         'PEIMS_CONSOLE_CLIENT_SECRET':'staging-secret-this-is-fake',
         'PEIMS_CONSOLE_COOKIE_KEY':Fernet.generate_key().decode('ascii')}
    for k,v in env.items():monkeypatch.setenv(k,v)
    ctx={'sub':'alice','aud':'peims-enterprise-web','nonce_override':None,'issuer_override':None,'expire':False}
    def fake_exchange(cfg,origin,code,verifier):
        assert cfg['PEIMS_CONSOLE_TOKEN_URL']==env['PEIMS_CONSOLE_TOKEN_URL']
        assert origin==env['PEIMS_CONSOLE_ORIGIN']
        assert 30<=len(verifier)<=128
        n=ctx['nonce_override'] or ctx['nonce']
        now=datetime.now(timezone.utc)
        claims={'sub':ctx['sub'],'iss':ctx['issuer_override'] or env['PEIMS_OIDC_ISSUER'],
                'aud':ctx['aud'],'nonce':n,'iat':now,
                'exp':now+(timedelta(seconds=-90) if ctx['expire'] else timedelta(minutes=30))}
        return {'id_token':jwt.encode(claims,private,algorithm='RS256')}
    monkeypatch.setattr(console,'_exchange_code',fake_exchange)
    with TestClient(app,base_url=env['PEIMS_CONSOLE_ORIGIN'],follow_redirects=False) as client:
        yield client,engine,env,ctx
    app.dependency_overrides.clear()
    engine.dispose()


def login(client,ctx):
    response=client.get('/console/login')
    assert response.status_code==303,response.text
    location=response.headers['location']
    params=parse_qs(urlsplit(location).query)
    assert params['code_challenge_method']==['S256']
    assert params['scope']==['openid profile']
    assert 'client_secret' not in location
    ctx['nonce']=params['nonce'][0]
    cb=client.get('/console/callback',params={'code':'fake-code','state':params['state'][0]})
    return cb


def test_unconfigured_console_denies_sign_in_but_serves_safe_assets(setup,monkeypatch):
    c,engine,env,ctx=setup
    p=c.get('/console/')
    assert p.status_code==200 and 'Enterprise Workspace' in p.text
    assert p.headers['x-frame-options']=='DENY'
    assert "script-src 'self'" in p.headers['content-security-policy']
    assert c.get('/console/assets/console.js').status_code==200
    assert c.get('/console/assets/console.css').status_code==200
    assert c.get('/console/api/session').status_code==401
    assert c.post('/console/api/logout').status_code==401
    monkeypatch.delenv('PEIMS_CONSOLE_CLIENT_SECRET')
    assert c.get('/console/login').status_code==503
    assert c.get('/console/api/projects/P1/tasks').status_code==401


def test_login_session_permanent_task_and_collaboration(setup):
    c,engine,env,ctx=setup
    cb=login(c,ctx)
    assert cb.status_code==303,cb.text
    assert cb.headers['location']=='/console/'
    assert 'access_token' not in str(c.cookies)
    assert c.cookies.get(console.SESSION_COOKIE)
    s=c.get('/console/api/session')
    assert s.status_code==200,s.text
    data=s.json(); csrf=data['csrf']
    assert data['subject']=='alice'
    assert data['projects']==[{'id':'P1','title':'Electrical Substation Modernization','currency':'GHS','role':'manager'}]
    base='/console/api/projects/P1'
    assert c.get(base+'/summary').json()['total']==0
    payload={'reference':'TASK-001','title':'Review substation relay protection',
             'kind':'task','start_date':'2026-11-10','due_date':'2026-11-20',
             'assigned_sub':'bob','estimate_hours':6}
    assert c.post(base+'/tasks',json=payload).status_code==403  # missing CSRF
    assert c.post(base+'/tasks',json=payload,headers={'X-PEIMS-CSRF':'forged'}).status_code==403
    assert c.post(base+'/tasks',json=payload,headers={'X-PEIMS-CSRF':csrf,'Origin':'https://evil.test'}).status_code==403
    res=c.post(base+'/tasks',json=payload,headers={'X-PEIMS-CSRF':csrf,'Origin':env['PEIMS_CONSOLE_ORIGIN']})
    assert res.status_code==201,res.text
    task=res.json();item=task['id']
    assert task['created_by']=='alice' and task['assigned_sub']=='bob'
    assert c.get(base+'/tasks').json()[0]['id']==item
    assert c.get(base+'/tasks?limit=201').status_code==422
    assert c.get('/console/api/projects/P2/tasks').status_code==404
    edit=c.patch(f'{base}/tasks/{item}',json={'expected_version':1,'status':'in_progress','progress_pct':50},headers={'X-PEIMS-CSRF':csrf})
    assert edit.status_code==200,edit.text
    assert edit.json()['version']==2
    stale=c.patch(f'{base}/tasks/{item}',json={'expected_version':1,'status':'done'},headers={'X-PEIMS-CSRF':csrf})
    assert stale.status_code==409
    root=f'{base}/tasks/{item}'
    comment=c.post(root+'/comments',json={'body':'Please verify the updated protection scheme.'},headers={'X-PEIMS-CSRF':csrf})
    assert comment.status_code==201,comment.text
    assert comment.json()['author_sub']=='alice'
    assert c.get(root+'/comments').json()[0]['body'].startswith('Please verify')
    time=c.post(root+'/time',json={'work_date':'2026-11-10','hours':2.5},headers={'X-PEIMS-CSRF':csrf})
    assert time.status_code==201,time.text
    assert c.get(root+'/time').json()[0]['actor_sub']=='alice'
    assert c.get(base+'/summary').json()['logged_hours']=='2.50'
    with Session(engine) as db:
        assert db.get(WorkItem,item).version==2
        assert db.scalar(select(WorkComment).where(WorkComment.work_item_id==item)).author_sub=='alice'
        assert len(list(db.scalars(select(AuditEvent).where(AuditEvent.project_id=='P1'))))>=4
        stored=db.scalar(select(BrowserSession))
        assert stored.sid_hash != c.cookies.get(console.SESSION_COOKIE)
        assert len(stored.sid_hash)==64
    assert c.post('/console/api/logout',json={}).status_code==403
    assert c.post('/console/api/logout',json={},headers={'X-PEIMS-CSRF':csrf}).status_code==204
    assert c.get('/console/api/session').status_code==401


def test_viewer_permissions_expiry_and_project_revocation(setup):
    c,engine,env,ctx=setup
    ctx['sub']='reader'
    assert login(c,ctx).status_code==303
    csrf=c.get('/console/api/session').json()['csrf']
    root='/console/api/projects/P1'
    assert c.get(root+'/tasks').status_code==200
    data={'reference':'FAIL','title':'Readers cannot edit','start_date':'2026-11-10','due_date':'2026-11-10'}
    assert c.post(root+'/tasks',json=data,headers={'X-PEIMS-CSRF':csrf}).status_code==403
    assert c.get('/console/api/projects/P2/summary').status_code==404
    with Session(engine) as db:
        db.delete(db.get(Member,('P1','reader')));db.commit()
    assert c.get(root+'/tasks').status_code==404
    with Session(engine) as db:
        bs=db.scalar(select(BrowserSession));bs.expires_at=datetime.now(timezone.utc)-timedelta(seconds=30);db.commit()
    assert c.get('/console/api/session').status_code==401


def test_oidc_flow_mismatch_and_bad_claims_rejected(setup):
    c,engine,env,ctx=setup
    attempt=c.get('/console/login')
    q=parse_qs(urlsplit(attempt.headers['location']).query)
    state=q['state'][0];ctx['nonce']=q['nonce'][0]
    assert c.get('/console/callback',params={'state':'wrong','code':'fake-code'}).status_code==401
    ctx['nonce_override']='wrong-nonce'
    assert c.get('/console/callback',params={'state':state,'code':'fake-code'}).status_code==401
    ctx['nonce_override']=None
    ctx['aud']='wrong-client'
    assert c.get('/console/callback',params={'state':state,'code':'fake-code'}).status_code==401
    ctx['aud']=env['PEIMS_CONSOLE_CLIENT_ID'];ctx['expire']=True
    assert c.get('/console/callback',params={'state':state,'code':'fake-code'}).status_code==401
    with Session(engine) as db:
        assert db.scalar(select(BrowserSession)) is None
    assert c.get('/console/api/session').status_code==401


def test_console_assets_no_hardcoded_secrets_or_unsafe_html(setup):
    c,_,env,_=setup
    script=c.get('/console/assets/console.js').text
    assert 'innerHTML' not in script
    assert 'localStorage' in script  # only a comment explaining it is intentionally absent
    assert 'client_secret' not in script.lower()
    assert 'document.cookie' not in script
    assert 'X-PEIMS-CSRF' in script
    assert 'PEIMS_CONSOLE_CLIENT_SECRET' not in script
    assert "[hidden]{display:none!important}" in c.get('/console/assets/console.css').text


def test_session_cookie_tamper_and_callback_replay_fail(setup):
    c,engine,env,ctx=setup
    flow=c.get('/console/login')
    params=parse_qs(urlsplit(flow.headers['location']).query)
    ctx['nonce']=params['nonce'][0]
    callback_url='/console/callback'
    cb=c.get(callback_url,params={'code':'valid','state':params['state'][0]})
    assert cb.status_code==303
    sid=c.cookies.get(console.SESSION_COOKIE)
    assert c.get(callback_url,params={'code':'replayed','state':params['state'][0]}).status_code==401
    assert c.get('/console/api/session').status_code==200
    c.cookies.set(console.SESSION_COOKIE,'forged-opaque-cookie',domain='console.example.test',path='/')
    assert c.get('/console/api/session').status_code==401


def test_http_origin_and_weakened_identity_settings_fail_closed(setup,monkeypatch):
    c,_,env,_=setup
    monkeypatch.setenv('PEIMS_CONSOLE_ORIGIN','http://console.example.test')
    assert c.get('/console/login').status_code==503
    monkeypatch.setenv('PEIMS_CONSOLE_ORIGIN',env['PEIMS_CONSOLE_ORIGIN'])
    monkeypatch.setenv('PEIMS_CONSOLE_COOKIE_KEY','not-a-valid-fernet-key')
    assert c.get('/console/login').status_code==503
