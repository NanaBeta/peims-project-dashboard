"""Real PostgreSQL checks for the free-hosting adapter.

Run only against a throwaway CI database:
  PEIMS_EPHEMERAL_POSTGRES_TEST=yes python -m scripts.free_postgres_acceptance

Never run this script against a shared, production or user-data database.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, text

from free_workspace_postgres import PostgresWorkspaceStore
from free_workspace_store import AccessDenied, MissingRecord, Principal, RevisionConflict


def must_fail(exception, fn):
    try:
        fn()
    except exception:
        return
    raise AssertionError(f"Expected {exception.__name__}")


def main():
    if os.environ.get("PEIMS_EPHEMERAL_POSTGRES_TEST") != "yes":
        raise SystemExit("Requires explicit disposable PostgreSQL CI marker")
    url = os.environ["PEIMS_DATABASE_URL"]
    if "127.0.0.1" not in url or "peims_stage" not in url:
        raise SystemExit("Refusing non-local or non-CI test database")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA peims_free_ci"))
            conn.execute(text("""
                CREATE TABLE peims_free_ci.peims_free_memberships (
                    subject text NOT NULL,
                    project_id text NOT NULL,
                    role text NOT NULL CHECK(role IN ('viewer','engineer','manager')),
                    PRIMARY KEY(subject, project_id)
                )
            """))
            conn.execute(text("""
                CREATE TABLE peims_free_ci.peims_free_records (
                    project_id text NOT NULL,
                    record_id text NOT NULL,
                    revision integer NOT NULL CHECK(revision > 0),
                    data jsonb NOT NULL,
                    PRIMARY KEY(project_id, record_id)
                )
            """))
            conn.execute(text("""
                INSERT INTO peims_free_ci.peims_free_memberships
                (subject, project_id, role) VALUES
                ('alice','P1','manager'), ('bob','P1','engineer'),
                ('viewer','P1','viewer'), ('charlie','P2','manager')
            """))
        first = PostgresWorkspaceStore(engine, schema="peims_free_ci")
        alice, bob, viewer, charlie = (Principal(n) for n in ("alice", "bob", "viewer", "charlie"))
        created = first.put(alice, "P1", "task", {"name": "initial"}, expected_revision=None)
        assert created.revision == 1
        # Reconstructed store to demonstrate state is in PostgreSQL, not object memory.
        second = PostgresWorkspaceStore(engine, schema="peims_free_ci")
        assert second.get(bob, "P1", "task").data == {"name": "initial"}
        must_fail(AccessDenied, lambda: second.get(charlie, "P1", "task"))
        must_fail(AccessDenied, lambda: second.put(viewer, "P1", "task", {}, expected_revision=1))
        must_fail(AccessDenied, lambda: second.put(bob, "P2", "task", {}, expected_revision=None))
        must_fail(MissingRecord, lambda: second.get(alice, "P1", "absent"))
        changed = second.put(bob, "P1", "task", {"name": "updated"}, expected_revision=1)
        assert changed.revision == 2
        must_fail(RevisionConflict, lambda: second.put(alice, "P1", "task", {}, expected_revision=1))
        must_fail(RevisionConflict, lambda: second.put(alice, "P1", "task", {}, expected_revision=None))
        assert second.get(alice, "P1", "task").data["name"] == "updated"
        # Two writers racing on the same revision: exactly one must win.
        def race(idx):
            try:
                return second.put(bob, "P1", "task", {"writer": idx}, expected_revision=2)
            except RevisionConflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(race, (1, 2)))
        assert sum(x is not None for x in outcomes) == 1
        assert second.get(alice, "P1", "task").revision == 3
        print("Free PostgreSQL adapter acceptance passed: persistence, isolation, roles, CAS race.")
    finally:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS peims_free_ci CASCADE"))
        engine.dispose()


if __name__ == "__main__":
    main()
