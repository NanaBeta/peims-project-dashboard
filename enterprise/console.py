"""PEIMS v0.8.1: same-origin, OIDC-authenticated enterprise console.

No browser access tokens. The console authenticates once via authorization code +
PKCE, verifies an OIDC ID token server-side and persists only an opaque, hashed
session handle in PostgreSQL. Existing project service handlers enforce RBAC.

Requires a confidential OIDC client, TLS and database migrations. Does not
modify or authenticate the public Streamlit demo.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlencode, urlsplit
import base64
import hmac
import os
import secrets

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from enterprise.auth import Identity, jwks_client
from enterprise.database import get_db
from enterprise.models import BrowserSession, Project, Member
from enterprise.permissions import membership
from enterprise import work_management as work

router = APIRouter()
assets_root = Path(__file__).resolve().parent / 'console_assets'
assets = StaticFiles(directory=str(assets_root), check_dir=True)
SESSION_COOKIE = '__Host-peims'
FLOW_COOKIE = '__Host-peims-oauth'
SESSION_SECONDS = 3600
FLOW_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(value: str) -> str:
    return sha256(value.encode('utf-8')).hexdigest()


def _base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _valid_https(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and not parsed.username and not parsed.password and not parsed.fragment)
    except ValueError:
        return False


def _config():
    # No implicit demo values. A separate confidential OAuth client is needed.
    names = ('PEIMS_CONSOLE_ORIGIN', 'PEIMS_OIDC_ISSUER', 'PEIMS_OIDC_JWKS_URL',
             'PEIMS_CONSOLE_AUTHORIZE_URL', 'PEIMS_CONSOLE_TOKEN_URL',
             'PEIMS_CONSOLE_CLIENT_ID', 'PEIMS_CONSOLE_CLIENT_SECRET',
             'PEIMS_CONSOLE_COOKIE_KEY')
    env = {name: os.getenv(name, '').strip() for name in names}
    if not all(env.values()) or not all(_valid_https(env[name]) for name in (
       'PEIMS_CONSOLE_ORIGIN', 'PEIMS_OIDC_ISSUER', 'PEIMS_OIDC_JWKS_URL',
       'PEIMS_CONSOLE_AUTHORIZE_URL', 'PEIMS_CONSOLE_TOKEN_URL')):
        raise HTTPException(status_code=503, detail='Enterprise login is not configured')
    origin = env['PEIMS_CONSOLE_ORIGIN'].rstrip('/')
    parsed = urlsplit(origin)
    if parsed.path or parsed.query or parsed.fragment:
        raise HTTPException(status_code=503, detail='Invalid enterprise console origin')
    try:
        cipher = Fernet(env['PEIMS_CONSOLE_COOKIE_KEY'].encode('ascii'))
    except Exception:
        raise HTTPException(status_code=503, detail='Invalid enterprise console key') from None
    if len(env['PEIMS_CONSOLE_CLIENT_ID']) > 255 or len(env['PEIMS_CONSOLE_CLIENT_SECRET']) < 16:
        raise HTTPException(status_code=503, detail='Enterprise identity client is not configured')
    return env, origin, cipher


def _csrf(raw_session_id: str) -> str:
    env, _, _ = _config()
    return hmac.new(env['PEIMS_CONSOLE_COOKIE_KEY'].encode('ascii'),
                    ('csrf:' + raw_session_id).encode('ascii'), 'sha256').hexdigest()


def _authenticated(request: Request, db: Session = Depends(get_db)) -> Identity:
    sid = request.cookies.get(SESSION_COOKIE, '')
    if not 36 <= len(sid) <= 100 or not all(ch.isalnum() or ch in '-_' for ch in sid):
        raise HTTPException(status_code=401, detail='Sign in to the enterprise console')
    session = db.get(BrowserSession, _hash(sid))
    if session is None:
        raise HTTPException(status_code=401, detail='Session expired; sign in again')
    expiry = session.expires_at
    if (expiry if expiry.tzinfo else expiry.replace(tzinfo=timezone.utc)) <= _now():
        raise HTTPException(status_code=401, detail='Session expired; sign in again')
    return Identity(sub=session.principal_sub)


def _require_csrf(request: Request, identity: Identity = Depends(_authenticated)) -> Identity:
    sid = request.cookies.get(SESSION_COOKIE, '')
    submitted = request.headers.get('X-PEIMS-CSRF', '')
    if not submitted or not hmac.compare_digest(submitted, _csrf(sid)):
        raise HTTPException(status_code=403, detail='Request verification failed')
    origin = request.headers.get('origin')
    if origin:
        _, configured_origin, _ = _config()
        if origin.rstrip('/') != configured_origin:
            raise HTTPException(status_code=403, detail='Request origin rejected')
    # State-changing console routes only accept JSON through typed Pydantic bodies.
    return identity


def _json(row, schema):
    return schema.model_validate(row).model_dump(mode='json')


@router.get('/console', include_in_schema=False)
@router.get('/console/', include_in_schema=False)
def console_page():
    return FileResponse(assets_root / 'index.html', media_type='text/html',
                        headers={'Cache-Control': 'no-store'})


@router.get('/console/login', include_in_schema=False)
def start_login():
    env, origin, cipher = _config()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(32)
    binding = secrets.token_urlsafe(32)
    packed = '|'.join([state, verifier, nonce, binding])
    params = {
        'client_id': env['PEIMS_CONSOLE_CLIENT_ID'],
        'response_type': 'code', 'response_mode': 'query',
        'redirect_uri': origin + '/console/callback',
        'scope': 'openid profile', 'state': state, 'nonce': nonce,
        'code_challenge': _base64(sha256(verifier.encode('ascii')).digest()),
        'code_challenge_method': 'S256',
    }
    destination = env['PEIMS_CONSOLE_AUTHORIZE_URL']
    destination += ('&' if '?' in destination else '?') + urlencode(params)
    resp = RedirectResponse(destination, status_code=303,
                            headers={'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
    resp.set_cookie(FLOW_COOKIE, cipher.encrypt(packed.encode('ascii')).decode('ascii'),
                    max_age=FLOW_SECONDS, secure=True, httponly=True, samesite='lax', path='/')
    # Separate binding cookie defeats an attacker swapping a complete flow cookie
    # to trigger a login-CSRF/session-substitution attack.
    resp.set_cookie('__Host-peims-binding', binding, max_age=FLOW_SECONDS,
                    secure=True, httponly=True, samesite='lax', path='/')
    return resp



def _exchange_code(env: dict, origin: str, code: str, verifier: str) -> dict:
    # Confidential-client exchange happens on the server; never expose tokens.
    with httpx.Client(timeout=8, follow_redirects=False) as client:
        response = client.post(env['PEIMS_CONSOLE_TOKEN_URL'], data={
            'grant_type':'authorization_code', 'code':code,
            'redirect_uri':origin+'/console/callback',
            'client_id':env['PEIMS_CONSOLE_CLIENT_ID'],
            'client_secret':env['PEIMS_CONSOLE_CLIENT_SECRET'],
            'code_verifier':verifier,
        })
    response.raise_for_status()
    return response.json()

@router.get('/console/callback', include_in_schema=False)
def callback(request: Request, code: str = '', state: str = '',
             error: str = '', db: Session = Depends(get_db)):
    env, origin, cipher = _config()
    if error:
        raise HTTPException(status_code=401, detail='Identity provider declined sign-in')
    if not code or len(code) > 4096 or not state or len(state) > 128:
        raise HTTPException(status_code=400, detail='Missing authorization response')
    cookie = request.cookies.get(FLOW_COOKIE, '')
    binding_cookie = request.cookies.get('__Host-peims-binding', '')
    try:
        packed = cipher.decrypt(cookie.encode('ascii'), ttl=FLOW_SECONDS).decode('ascii').split('|')
    except (InvalidToken, ValueError, UnicodeError):
        raise HTTPException(status_code=401, detail='Sign-in challenge expired') from None
    if (len(packed) != 4 or not hmac.compare_digest(packed[0], state)
            or not binding_cookie or not hmac.compare_digest(packed[3], binding_cookie)):
        raise HTTPException(status_code=401, detail='Sign-in challenge mismatch')
    _, verifier, nonce, _ = packed
    try:
        id_token = _exchange_code(env, origin, code, verifier).get('id_token', '')
        if not isinstance(id_token, str) or len(id_token) > 12000:
            raise ValueError('Missing ID token')
        signing_key = jwks_client(env['PEIMS_OIDC_JWKS_URL']).get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, signing_key, algorithms=['RS256'],
                            audience=env['PEIMS_CONSOLE_CLIENT_ID'],
                            issuer=env['PEIMS_OIDC_ISSUER'], leeway=30,
                            options={'require':['sub','iss','aud','iat','exp','nonce']})
        subject = claims.get('sub')
        if (not isinstance(subject, str) or not 1 <= len(subject) <= 255
                or not hmac.compare_digest(str(claims['nonce']), nonce)):
            raise ValueError('Invalid subject or nonce')
        expiry = min(int(claims['exp']), int(_now().timestamp()) + SESSION_SECONDS)
        if expiry <= _now().timestamp():
            raise ValueError('Expired identity')
    except Exception:
        raise HTTPException(status_code=401, detail='Identity verification failed') from None
    sid = secrets.token_urlsafe(40)
    old_sid = request.cookies.get(SESSION_COOKIE, '')
    if old_sid:
        db.query(BrowserSession).filter(BrowserSession.sid_hash==_hash(old_sid)).delete()
    db.add(BrowserSession(sid_hash=_hash(sid), principal_sub=subject,
                          expires_at=datetime.fromtimestamp(expiry, tz=timezone.utc)))
    db.commit()
    resp = RedirectResponse('/console/', status_code=303,
                            headers={'Cache-Control':'no-store', 'Referrer-Policy':'no-referrer'})
    resp.set_cookie(SESSION_COOKIE, sid, max_age=max(1, expiry-int(_now().timestamp())),
                    secure=True, httponly=True, samesite='lax', path='/')
    resp.delete_cookie(FLOW_COOKIE, path='/', secure=True, httponly=True, samesite='lax')
    resp.delete_cookie('__Host-peims-binding', path='/', secure=True, httponly=True, samesite='lax')
    return resp


@router.get('/console/api/session', include_in_schema=False)
def get_console_session(request: Request, identity: Identity=Depends(_authenticated),
                        db: Session=Depends(get_db)):
    projects = db.execute(select(Project, Member.role).join(Member, Member.project_id==Project.id)
                          .where(Member.principal_sub==identity.sub).order_by(Project.title)).all()
    return {'subject': identity.sub, 'csrf': _csrf(request.cookies[SESSION_COOKIE]),
            'projects': [{'id':p.id,'title':p.title,'currency':p.currency,'role':role}
                         for p,role in projects]}


@router.post('/console/api/logout', include_in_schema=False)
def logout(request: Request, identity: Identity=Depends(_require_csrf),
           db: Session=Depends(get_db)):
    db.query(BrowserSession).filter(BrowserSession.sid_hash==_hash(request.cookies[SESSION_COOKIE])).delete()
    db.commit()
    resp = Response(status_code=204, headers={'Cache-Control':'no-store'})
    resp.delete_cookie(SESSION_COOKIE, path='/', secure=True, httponly=True, samesite='lax')
    return resp


@router.get('/console/api/projects/{project_id}/summary', include_in_schema=False)
def project_summary(project_id: str, identity: Identity=Depends(_authenticated),
                    db: Session=Depends(get_db)):
    return work.work_summary(project_id,identity,db)


@router.get('/console/api/projects/{project_id}/tasks', include_in_schema=False)
def tasks(project_id:str,limit:int=Query(default=100,ge=1,le=200),
          offset:int=Query(default=0,ge=0,le=100000),
          identity:Identity=Depends(_authenticated),db:Session=Depends(get_db)):
    items = work.list_work_items(project_id,limit,offset,None,identity,db)
    return [_json(item,work.WorkItemOut) for item in items]


@router.post('/console/api/projects/{project_id}/tasks', status_code=201, include_in_schema=False)
def add_task(project_id:str, payload:work.WorkCreate,
             identity:Identity=Depends(_require_csrf),db:Session=Depends(get_db)):
    return _json(work.create_work_item(project_id,payload,identity,db),work.WorkItemOut)


@router.get('/console/api/projects/{project_id}/tasks/{task_id}', include_in_schema=False)
def get_task(project_id:str,task_id:str,identity:Identity=Depends(_authenticated),db:Session=Depends(get_db)):
    return _json(work.get_work_item(project_id,task_id,identity,db),work.WorkItemOut)


@router.patch('/console/api/projects/{project_id}/tasks/{task_id}', include_in_schema=False)
def edit_task(project_id:str,task_id:str,payload:work.WorkEdit,
              identity:Identity=Depends(_require_csrf),db:Session=Depends(get_db)):
    return _json(work.edit_work_item(project_id,task_id,payload,identity,db),work.WorkItemOut)


@router.get('/console/api/projects/{project_id}/tasks/{task_id}/comments', include_in_schema=False)
def comments(project_id:str,task_id:str,identity:Identity=Depends(_authenticated),db:Session=Depends(get_db)):
    return [_json(row,work.CommentOut) for row in work.list_comments(project_id,task_id,100,0,identity,db)]


@router.post('/console/api/projects/{project_id}/tasks/{task_id}/comments', status_code=201, include_in_schema=False)
def add_comment(project_id:str,task_id:str,payload:work.CommentCreate,
                identity:Identity=Depends(_require_csrf),db:Session=Depends(get_db)):
    return _json(work.post_comment(project_id,task_id,payload,identity,db),work.CommentOut)


@router.get('/console/api/projects/{project_id}/tasks/{task_id}/time', include_in_schema=False)
def time_entries(project_id:str,task_id:str,identity:Identity=Depends(_authenticated),db:Session=Depends(get_db)):
    return [_json(row,work.TimeOut) for row in work.list_time_entries(project_id,task_id,100,0,identity,db)]


@router.post('/console/api/projects/{project_id}/tasks/{task_id}/time', status_code=201, include_in_schema=False)
def add_time_entry(project_id:str,task_id:str,payload:work.TimeCreate,
                   identity:Identity=Depends(_require_csrf),db:Session=Depends(get_db)):
    return _json(work.add_time_entry(project_id,task_id,payload,identity,db),work.TimeOut)


@router.get('/console/api/projects/{project_id}/tasks/{task_id}/predecessors', include_in_schema=False)
def predecessors(project_id:str,task_id:str,identity:Identity=Depends(_authenticated),db:Session=Depends(get_db)):
    return [_json(row,work.DependencyOut) for row in work.list_predecessors(project_id,task_id,identity,db)]


@router.post('/console/api/projects/{project_id}/tasks/{task_id}/predecessors', status_code=201, include_in_schema=False)
def add_dep(project_id:str,task_id:str,payload:work.PredecessorCreate,
            identity:Identity=Depends(_require_csrf),db:Session=Depends(get_db)):
    return _json(work.add_predecessor(project_id,task_id,payload,identity,db),work.DependencyOut)


@router.delete('/console/api/projects/{project_id}/tasks/{task_id}/predecessors/{predecessor_id}',
               status_code=204, include_in_schema=False)
def remove_dep(project_id:str,task_id:str,predecessor_id:str,
               identity:Identity=Depends(_require_csrf),db:Session=Depends(get_db)):
    return work.remove_predecessor(project_id,task_id,predecessor_id,identity,db)
