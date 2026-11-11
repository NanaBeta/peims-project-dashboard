"""PostgreSQL adapter for the future authenticated PEIMS Streamlit workspace.

Not wired into app.py. Expects pre-provisioned workspace tables and verified
server-side Principal identities; NEVER construct Principal from a user textbox.
Uses SQL transactions, per-project membership checks and compare-and-swap writes.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.engine import Engine

from free_workspace_store import AccessDenied, MissingRecord, Principal, RevisionConflict, Snapshot


class PostgresWorkspaceStore:
    """Server-side adapter; connection privileges must be kept in Streamlit secrets.

    This is an application authorization boundary, not database row-level security.
    A later deployment must review DB roles, RLS and backup/recovery separately.
    """

    def __init__(self, engine: Engine, *, schema: str = "public") -> None:
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
            raise ValueError("Invalid SQL schema identifier")
        if engine.dialect.name != "postgresql":
            raise ValueError("PostgresWorkspaceStore requires PostgreSQL")
        self._engine = engine
        self._members = f'"{schema}".peims_free_memberships'
        self._records = f'"{schema}".peims_free_records'

    def _authorize(self, conn, actor: Principal, project_id: str, *, write: bool) -> None:
        role = conn.execute(text(
            f"SELECT role FROM {self._members} "
            "WHERE subject = :subject AND project_id = :project_id FOR SHARE"
        ), {"subject": actor.subject, "project_id": project_id}).scalar_one_or_none()
        if role not in ("viewer", "engineer", "manager") or (write and role == "viewer"):
            raise AccessDenied("Project access denied")

    @staticmethod
    def _snapshot(row: Any) -> Snapshot:
        return Snapshot(
            project_id=row["project_id"], record_id=row["record_id"],
            revision=row["revision"], data=row["data"]
        )

    def get(self, actor: Principal, project_id: str, record_id: str) -> Snapshot:
        if not project_id or not record_id:
            raise ValueError("Project and record IDs are required")
        with self._engine.begin() as conn:
            self._authorize(conn, actor, project_id, write=False)
            row = conn.execute(text(
                f"SELECT project_id, record_id, revision, data FROM {self._records} "
                "WHERE project_id = :project_id AND record_id = :record_id"
            ), {"project_id": project_id, "record_id": record_id}).mappings().first()
            if row is None:
                raise MissingRecord("Record not found")
            return self._snapshot(row)

    def put(self, actor: Principal, project_id: str, record_id: str,
            data: Mapping[str, Any], *, expected_revision: int | None) -> Snapshot:
        if not project_id or not record_id:
            raise ValueError("Project and record IDs are required")
        if not isinstance(data, Mapping):
            raise TypeError("Record data must be a mapping")
        payload = json.dumps(dict(data), allow_nan=False)
        params = {"project_id": project_id, "record_id": record_id,
                  "payload": payload, "expected_revision": expected_revision}
        with self._engine.begin() as conn:
            self._authorize(conn, actor, project_id, write=True)
            if expected_revision is None:
                row = conn.execute(text(
                    f"INSERT INTO {self._records} (project_id, record_id, revision, data) "
                    "VALUES (:project_id, :record_id, 1, CAST(:payload AS jsonb)) "
                    "ON CONFLICT (project_id, record_id) DO NOTHING "
                    "RETURNING project_id, record_id, revision, data"
                ), params).mappings().first()
            else:
                if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 1:
                    raise ValueError("Expected revision must be a positive integer")
                row = conn.execute(text(
                    f"UPDATE {self._records} SET revision = revision + 1, "
                    "data = CAST(:payload AS jsonb) "
                    "WHERE project_id = :project_id AND record_id = :record_id "
                    "AND revision = :expected_revision "
                    "RETURNING project_id, record_id, revision, data"
                ), params).mappings().first()
            if row is None:
                raise RevisionConflict("Record changed or already exists")
            return self._snapshot(row)
