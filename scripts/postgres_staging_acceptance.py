"""Disposable PostgreSQL+TLS acceptance test, for GitHub Actions only.

This script exercises the *real* Alembic schema and API using fictional records.
Never point it at a customer database or an already-provisioned environment.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise.auth import Identity, get_identity
from enterprise.main import app
from enterprise.models import AuditEvent, Member, Project, WorkDependency, WorkItem

EXPECTED_REVISION = "0005_console_sessions"


def require_ephemeral_ci() -> str:
    if os.getenv("PEIMS_EPHEMERAL_POSTGRES_TEST") != "yes" or os.getenv("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Refusing to run destructive test outside isolated CI")
    url = os.getenv("PEIMS_DATABASE_URL", "")
    if "127.0.0.1:5432/peims_stage" not in url or "sslmode=require" not in url:
        raise RuntimeError("Refusing non-ephemeral or non-TLS database target")
    return url


def payload(reference: str, *, assigned_sub: str = "ci-engineer") -> dict:
    return {
        "reference": reference,
        "title": "Fictional electrical commissioning task",
        "kind": "task",
        "status": "todo",
        "priority": "medium",
        "assigned_sub": assigned_sub,
        "description": "Disposable CI only",
        "start_date": "2026-11-11",
        "due_date": "2026-11-14",
        "estimate_hours": "8.00",
        "progress_pct": "0",
    }


def main() -> None:
    url = require_ephemeral_ci()
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == EXPECTED_REVISION
            assert connection.execute(
                text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            ).scalar_one() is True, "PostgreSQL connection must use TLS"
            assert connection.execute(text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN "
                "('work_items','work_dependencies','work_time_entries','work_comments','browser_sessions')"
            )).scalar_one() == 5

        with Session(engine) as db:
            db.add_all([
                Project(id="CI-A", title="CI A - Fictional", currency="GHS"),
                Project(id="CI-B", title="CI B - Fictional", currency="GHS"),
            ])
            db.flush()
            db.add_all([
                Member(project_id="CI-A", principal_sub="ci-manager", role="manager"),
                Member(project_id="CI-A", principal_sub="ci-engineer", role="engineer"),
                Member(project_id="CI-A", principal_sub="ci-viewer", role="viewer"),
                Member(project_id="CI-B", principal_sub="ci-other", role="manager"),
            ])
            db.commit()

        def user(sub: str) -> None:
            app.dependency_overrides[get_identity] = lambda: Identity(sub=sub)

        with TestClient(app) as client:
            user("ci-engineer")
            created = client.post("/v1/projects/CI-A/work-items", json=payload("CI-T-1"))
            assert created.status_code == 201, created.text
            a = created.json()
            assert a["project_id"] == "CI-A" and a["created_by"] == "ci-engineer"
            item_id = a["id"]
            patched = client.patch(f"/v1/projects/CI-A/work-items/{item_id}",
                                   json={"expected_version": 1, "status": "in_progress", "progress_pct": "25"})
            assert patched.status_code == 200, patched.text
            assert patched.json()["version"] == 2
            stale = client.patch(f"/v1/projects/CI-A/work-items/{item_id}",
                                 json={"expected_version": 1, "priority": "high"})
            assert stale.status_code == 409

            comment = client.post(f"/v1/projects/CI-A/work-items/{item_id}/comments",
                                  json={"body": "CI review comment"})
            assert comment.status_code == 201 and comment.json()["author_sub"] == "ci-engineer"
            hours = client.post(f"/v1/projects/CI-A/work-items/{item_id}/time-entries",
                                json={"work_date": "2026-11-11", "hours": "1.50", "note": "CI"})
            assert hours.status_code == 201 and hours.json()["actor_sub"] == "ci-engineer"

            user("ci-viewer")
            assert client.get(f"/v1/projects/CI-A/work-items/{item_id}").status_code == 200
            assert client.post("/v1/projects/CI-A/work-items", json=payload("CI-DENY")).status_code == 403
            user("ci-other")
            assert client.get(f"/v1/projects/CI-A/work-items/{item_id}").status_code == 404
            foreign = client.post("/v1/projects/CI-B/work-items",
                                  json=payload("CI-FOREIGN", assigned_sub="ci-other"))
            assert foreign.status_code == 201, foreign.text
            foreign_id = foreign.json()["id"]

            user("ci-engineer")
            assert client.get(f"/v1/projects/CI-A/work-items/{foreign_id}").status_code == 404

        # A new transaction reads committed records: they are not browser-session data.
        with Session(engine) as db:
            saved = db.get(WorkItem, item_id)
            assert saved is not None and saved.status == "in_progress" and saved.version == 2
            assert db.scalars(select(AuditEvent).where(
                AuditEvent.project_id == "CI-A", AuditEvent.actor_sub == "ci-engineer"
            )).first() is not None

        # PostgreSQL itself must reject a dependency pointing into a foreign project.
        with Session(engine) as db:
            db.add(WorkDependency(
                id=str(uuid4()), project_id="CI-A", predecessor_id=foreign_id,
                successor_id=item_id, created_by="ci-engineer",
            ))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
            else:
                raise AssertionError("Cross-project dependency bypassed PostgreSQL foreign keys")

        print("PostgreSQL TLS, Alembic, persistence, audit, RBAC, conflict and cross-project FK checks passed")
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


if __name__ == "__main__":
    main()
