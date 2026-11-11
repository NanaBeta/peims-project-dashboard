"""Storage-neutral, fail-closed project workspace interface.

This module is deliberately independent of Streamlit and enterprise hosting.
It is NOT a shared database or a Cloud deployment. The in-memory implementation
is suitable for isolated tests only, never multi-user production persistence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import RLock
from typing import Any, Mapping, Protocol


class AccessDenied(PermissionError):
    """Unknown membership or insufficient role."""


class RevisionConflict(ValueError):
    """A record was changed by another writer."""


class MissingRecord(LookupError):
    """No record is visible in the authorized project."""


@dataclass(frozen=True)
class Principal:
    """Verified identity from the trusted server-side authentication layer."""

    subject: str

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("A verified, nonblank subject is required")


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    record_id: str
    revision: int
    data: dict[str, Any]


class WorkspaceStore(Protocol):
    """Persistence implementations must enforce membership and compare-and-swap.

    Never trust project_id, role or subject taken directly from browser inputs.
    Production implementations must enforce access in the same DB transaction
    as record access, and use an atomic conditional update for revision checks.
    """

    def get(self, actor: Principal, project_id: str, record_id: str) -> Snapshot: ...
    def put(
        self, actor: Principal, project_id: str, record_id: str,
        data: Mapping[str, Any], *, expected_revision: int | None
    ) -> Snapshot: ...


class MemoryWorkspaceStore:
    """Test-only implementation. No persistence across process restarts.

    Memberships are explicitly injected by trusted test setup, never inferred
    from a request's claimed role. A lock protects atomic revision updates.
    """

    def __init__(self, memberships: Mapping[tuple[str, str], str]) -> None:
        allowed = {"viewer", "engineer", "manager"}
        if not all(role in allowed for role in memberships.values()):
            raise ValueError("Invalid membership role")
        self._memberships = dict(memberships)
        self._records: dict[tuple[str, str], Snapshot] = {}
        self._lock = RLock()

    def _authorize(self, actor: Principal, project_id: str, *, write: bool) -> None:
        role = self._memberships.get((actor.subject, project_id))
        if role is None or (write and role == "viewer"):
            raise AccessDenied("Project access denied")

    def get(self, actor: Principal, project_id: str, record_id: str) -> Snapshot:
        with self._lock:
            self._authorize(actor, project_id, write=False)
            found = self._records.get((project_id, record_id))
            if found is None:
                raise MissingRecord("Record not found")
            return deepcopy(found)

    def put(
        self, actor: Principal, project_id: str, record_id: str,
        data: Mapping[str, Any], *, expected_revision: int | None
    ) -> Snapshot:
        if not isinstance(data, Mapping):
            raise TypeError("Record data must be a mapping")
        if not project_id or not record_id:
            raise ValueError("Project and record IDs are required")
        with self._lock:
            self._authorize(actor, project_id, write=True)
            current = self._records.get((project_id, record_id))
            if current is None:
                if expected_revision is not None:
                    raise RevisionConflict("New records require no existing revision")
                revision = 1
            else:
                if expected_revision != current.revision:
                    raise RevisionConflict("Record has changed; refresh before saving")
                revision = current.revision + 1
            snapshot = Snapshot(project_id, record_id, revision, deepcopy(dict(data)))
            self._records[(project_id, record_id)] = snapshot
            return deepcopy(snapshot)
