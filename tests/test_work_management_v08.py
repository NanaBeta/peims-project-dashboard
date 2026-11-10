"""Persistent collaboration API: isolated file-backed database substitute.

Production requires OIDC + encrypted PostgreSQL; these tests deliberately
substitute authenticated identities and a disposable SQLite database only.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session

from enterprise.auth import get_identity, Identity
from enterprise.database import get_db
from enterprise.main import app
from enterprise.models import (
    Base, Project, Member, WorkItem, WorkDependency, WorkTimeEntry,
    WorkComment, AuditEvent, Activity,
)


@pytest.fixture
def enterprise(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path/'enterprise.sqlite'}",
                           connect_args={'check_same_thread':False})
    @event.listens_for(engine,'connect')
    def fk_on(dbapi_connection, _):
        cursor=dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Project(id='P1',title='Fictional Generator Upgrade',currency='GHS'),
            Project(id='P2',title='Independent Second Project',currency='GHS'),
        ])
        db.flush()
        db.add_all([
            Member(project_id='P1',principal_sub='mgr',role='manager'),
            Member(project_id='P1',principal_sub='eng',role='engineer'),
            Member(project_id='P1',principal_sub='reader',role='viewer'),
            Member(project_id='P2',principal_sub='other',role='manager'),
        ])
        db.commit()

    def get_test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db]=get_test_db
    app.dependency_overrides[get_identity]=lambda:Identity('mgr')
    try:
        with TestClient(app) as client:
            yield client,engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def login(name):
    app.dependency_overrides[get_identity]=lambda:Identity(name)


def task(reference='T-001',kind='task',parent_id=None,**changes):
    row={
        'reference':reference,'title':'Install protection relay','description':'Test work package',
        'kind':kind,'parent_id':parent_id,'assigned_sub':'eng',
        'status':'todo','priority':'high','start_date':'2026-11-11',
        'due_date':'2026-11-14','estimate_hours':8,'progress_pct':0,
    }
    row.update(changes)
    return row


def create(c,reference='T-001',**changes):
    return c.post('/v1/projects/P1/work-items',json=task(reference,**changes))


def test_persistent_tasks_and_versions(enterprise):
    c,engine=enterprise
    p=create(c)
    assert p.status_code==201,p.text
    work=p.json()
    assert work['version']==1 and work['project_id']=='P1'
    assert work['assigned_sub']=='eng' and work['created_by']=='mgr'
    assert c.get('/v1/projects/P1/work-items/'+work['id']).status_code==200
    assert len(c.get('/v1/projects/P1/work-items').json())==1
    assert create(c).status_code==409
    updated=c.patch(f"/v1/projects/P1/work-items/{work['id']}",json={'expected_version':1,'status':'done'})
    assert updated.status_code==200,updated.text
    assert updated.json()['progress_pct']=='100.00'
    assert updated.json()['version']==2
    assert c.patch(f"/v1/projects/P1/work-items/{work['id']}",json={'expected_version':1,'priority':'low'}).status_code==409
    with Session(engine) as db:
        row=db.get(WorkItem,work['id'])
        assert row.status=='done' and row.version==2
        assert db.scalar(select(Activity).where(Activity.project_id=='P1')) is None
        audit=list(db.scalars(select(AuditEvent).where(AuditEvent.project_id=='P1').order_by(AuditEvent.happened_at)))
        assert {e.event_type for e in audit}=={'work.created','work.updated'}
        assert all(e.actor_sub=='mgr' for e in audit)
    # New HTTP client and transaction read the same file-backed DB.
    with TestClient(app) as restarted:
        assert restarted.get('/v1/projects/P1/work-items/'+work['id']).json()['status']=='done'
    assert c.get('/v1/projects/P1/work-summary').json()['total']==1


def test_validations_and_milestone_subtask(enterprise):
    c,_=enterprise
    for invalid in [
        task(title='  '),task(due_date='2026-11-01'),task(progress_pct=150),
        task(estimate_hours=-1),task(status='done',progress_pct=25),
        task(kind='milestone',start_date='2026-11-11',due_date='2026-11-12'),
        task(kind='subtask'),task(assigned_sub='other'),
    ]:
        r=c.post('/v1/projects/P1/work-items',json=invalid)
        assert r.status_code==422,(r.status_code,r.text)
    parent=create(c)
    assert parent.status_code==201
    parent_id=parent.json()['id']
    sub=create(c,'T-002',kind='subtask',parent_id=parent_id)
    assert sub.status_code==201,sub.text
    milestone=create(c,'T-003',kind='milestone',start_date='2026-11-13',due_date='2026-11-13',estimate_hours=0)
    assert milestone.status_code==201,milestone.text
    bad=c.patch(f'/v1/projects/P1/work-items/{milestone.json()["id"]}',json={'expected_version':1,'estimate_hours':5})
    assert bad.status_code==422,bad.text
    assert c.get('/v1/projects/P1/work-summary').json()['milestones']==1
    assert c.get('/v1/projects/P1/work-items?status=todo').status_code==200
    assert c.get('/v1/projects/P1/work-items?limit=201').status_code==422
    assert c.get('/v1/projects/P1/work-items?offset=-1').status_code==422
    assert c.patch('/v1/projects/P1/work-items/'+parent_id,json={'expected_version':1}).status_code==422


def test_dependency_cycle_and_project_isolation(enterprise):
    c,engine=enterprise
    a=create(c,'T-01').json()['id']
    b=create(c,'T-02').json()['id']
    d=create(c,'T-03').json()['id']
    endpoint=lambda item:f'/v1/projects/P1/work-items/{item}/predecessors'
    edge=c.post(endpoint(b),json={'predecessor_id':a})
    assert edge.status_code==201,edge.text
    assert c.post(endpoint(d),json={'predecessor_id':b}).status_code==201
    assert c.post(endpoint(a),json={'predecessor_id':d}).status_code==422
    assert c.post(endpoint(a),json={'predecessor_id':a}).status_code==422
    assert c.post(endpoint(b),json={'predecessor_id':a}).status_code==409
    assert c.get(endpoint(b)).json()[0]['predecessor_id']==a
    assert c.delete(endpoint(b)+'/'+a).status_code==204
    assert c.get(endpoint(b)).json()==[]
    assert c.delete(endpoint(b)+'/'+a).status_code==404
    login('other')
    foreign=c.post('/v1/projects/P2/work-items',json=task('OTHER',assigned_sub='other'))
    assert foreign.status_code==201,foreign.text
    foreign_id=foreign.json()['id']
    login('mgr')
    assert c.post(endpoint(b),json={'predecessor_id':foreign_id}).status_code==404
    assert c.get('/v1/projects/P2/work-items').status_code==404
    assert c.get('/v1/projects/P1/work-items/'+foreign_id).status_code==404
    assert c.get(f'/v1/projects/P1/work-items/{foreign_id}/comments').status_code==404
    with Session(engine) as db:
        assert db.scalar(select(WorkDependency).where(WorkDependency.project_id=='P2')) is None


def test_collaboration_comments_and_time(enterprise):
    c,engine=enterprise
    created=create(c)
    item=created.json()['id']
    root=f'/v1/projects/P1/work-items/{item}'
    login('reader')
    assert c.get(root).status_code==200
    assert c.post(root+'/comments',json={'body':'Can you check this?'}).status_code==403
    assert c.post(root+'/time-entries',json={'work_date':'2026-11-11','hours':2}).status_code==403
    login('eng')
    comment=c.post(root+'/comments',json={'body':'  Checked. @mgr please review.  '})
    assert comment.status_code==201,comment.text
    assert comment.json()['body']=='Checked. @mgr please review.'
    assert comment.json()['author_sub']=='eng'
    assert c.post(root+'/comments',json={'body':'  '}).status_code==422
    assert c.get(root+'/comments').status_code==200
    log=c.post(root+'/time-entries',json={'work_date':'2026-11-11','hours':15.5,'note':'Site work'})
    assert log.status_code==201,log.text
    assert log.json()['actor_sub']=='eng'
    assert c.post(root+'/time-entries',json={'work_date':'2026-11-11','hours':9}).status_code==422
    assert c.post(root+'/time-entries',json={'work_date':'2026-11-12','hours':0}).status_code==422
    assert c.post(root+'/time-entries',json={'work_date':'2026-11-12','hours':25}).status_code==422
    assert c.post(root+'/time-entries',json={'work_date':'2026-11-12','hours':3}).status_code==201
    login('mgr')
    assert c.get(root+'/comments?limit=0').status_code==422
    assert c.get(root+'/time-entries?offset=-1').status_code==422
    assert len(c.get(root+'/time-entries').json())==2
    assert c.get('/v1/projects/P1/work-summary').json()['logged_hours']=='18.50'
    with Session(engine) as db:
        assert db.scalar(select(WorkTimeEntry).where(WorkTimeEntry.project_id=='P1')) is not None
        assert db.scalar(select(WorkComment).where(WorkComment.project_id=='P1')).author_sub=='eng'
        assert {e.event_type for e in db.scalars(select(AuditEvent).where(AuditEvent.project_id=='P1'))} >= {'work.comment_added','work.time_logged'}


def test_revocation_and_roles(enterprise):
    c,_=enterprise
    item=create(c).json()['id']
    assert c.delete('/v1/projects/P1/members/eng?expected_version=1').status_code==409
    login('reader')
    assert c.patch('/v1/projects/P1/work-items/'+item,json={'expected_version':1,'status':'done'}).status_code==403
    assert c.post('/v1/projects/P1/work-items',json=task('NEVER')).status_code==403
    assert c.get('/v1/projects/P1/work-items').status_code==200
    login('other')
    assert c.get('/v1/projects/P1/work-summary').status_code==404
    login('mgr')
    revised=c.patch('/v1/projects/P1/work-items/'+item,json={'expected_version':1,'assigned_sub':None})
    assert revised.status_code==200,revised.text
    assert c.delete('/v1/projects/P1/members/eng?expected_version=1').status_code==204
    assert c.post('/v1/projects/P1/work-items',json=task('NO',assigned_sub='eng')).status_code==422
    login('eng')
    assert c.get('/v1/projects/P1/work-items').status_code==404
    assert c.get('/v1/projects/P1/work-summary').status_code==404


def test_real_auth_is_required_outside_test_override(enterprise):
    c,_=enterprise
    app.dependency_overrides.pop(get_identity)
    assert c.get('/v1/projects/P1/work-items').status_code==401
    assert c.post('/v1/projects/P1/work-items',json=task()).status_code==401


def test_input_spoofing_and_database_fkeys_fail_closed(enterprise):
    from sqlalchemy.exc import IntegrityError
    from uuid import uuid4
    c,engine=enterprise
    assert c.get('/v1/projects/P1/work-summary').json()['total']==0
    assert c.post('/v1/projects/P1/work-items',json={**task(), 'project_id':'P2'}).status_code==422
    assert c.post('/v1/projects/P1/work-items',json={**task(), 'created_by':'somebody'}).status_code==422
    assert c.post('/v1/projects/P1/work-items',json=task(assigned_sub='reader')).status_code==422
    id1=create(c).json()['id']
    login('other')
    id2=c.post('/v1/projects/P2/work-items',json=task('SAME',assigned_sub='other')).json()['id']
    login('mgr')
    # The backend cannot be bypassed by direct SQL inserts that reference another tenant.
    with Session(engine) as db:
        db.add(WorkDependency(id=str(uuid4()),project_id='P1',predecessor_id=id2,
             successor_id=id1,created_by='mgr'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(WorkItem(id=str(uuid4()),project_id='P1',reference='ILLEGAL',
            title='Cross-tenant assignee',description='',kind='task',status='todo',
            priority='low',assigned_sub='other',parent_id=None,
            start_date=date(2026,11,11),due_date=date(2026,11,13),
            estimate_hours=Decimal('0'),progress_pct=Decimal('0'),
            version=1,created_by='mgr',updated_by='mgr'))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert c.get('/v1/projects/P1/work-items').json()[0]['id']==id1


def test_comments_do_not_generate_mentions_or_allow_impersonation(enterprise):
    c,_=enterprise
    id1=create(c).json()['id']
    root=f'/v1/projects/P1/work-items/{id1}/comments'
    login('eng')
    assert c.post(root,json={'body':'@reader please review','author_sub':'mgr'}).status_code==422
    posted=c.post(root,json={'body':'<script>alert(1)</script>'})
    assert posted.status_code==201
    assert posted.json()['body']=='<script>alert(1)</script>'
    # API returns JSON, not HTML. Future frontend must escape this string.
    assert posted.headers['content-type'].startswith('application/json')
    assert c.get(root).json()[0]['author_sub']=='eng'
