"""Contract tests for PEIMS' free workspace storage boundary."""
import pytest
from free_workspace_store import (
    AccessDenied, MemoryWorkspaceStore, MissingRecord, Principal, RevisionConflict,
)


@pytest.fixture
def store():
    return MemoryWorkspaceStore({
        ("alice", "P1"): "manager", ("bob", "P1"): "engineer",
        ("viewer", "P1"): "viewer", ("alice", "P2"): "viewer",
        ("charlie", "P2"): "manager",
    })


def test_write_and_read_from_independent_principals(store):
    record = store.put(Principal("alice"), "P1", "TASK-1",
                       {"title": "Design", "progress": 0}, expected_revision=None)
    assert record.revision == 1
    assert store.get(Principal("bob"), "P1", "TASK-1").data["title"] == "Design"


def test_viewer_cannot_write(store):
    with pytest.raises(AccessDenied):
        store.put(Principal("viewer"), "P1", "TASK-1", {}, expected_revision=None)


def test_other_project_access_is_denied_even_for_existing_record(store):
    store.put(Principal("alice"), "P1", "TASK-1", {"secret": True}, expected_revision=None)
    with pytest.raises(AccessDenied):
        store.get(Principal("charlie"), "P1", "TASK-1")
    with pytest.raises(AccessDenied):
        store.put(Principal("bob"), "P2", "TASK-1", {}, expected_revision=None)


def test_project_ids_are_part_of_record_key(store):
    store.put(Principal("alice"), "P1", "same", {"value": "one"}, expected_revision=None)
    store.put(Principal("charlie"), "P2", "same", {"value": "two"}, expected_revision=None)
    assert store.get(Principal("alice"), "P1", "same").data["value"] == "one"
    assert store.get(Principal("charlie"), "P2", "same").data["value"] == "two"


def test_conflict_prevents_lost_update(store):
    original = store.put(Principal("alice"), "P1", "TASK-1", {"a": 1},
                         expected_revision=None)
    updated = store.put(Principal("bob"), "P1", "TASK-1", {"a": 2},
                        expected_revision=original.revision)
    assert updated.revision == 2
    with pytest.raises(RevisionConflict):
        store.put(Principal("alice"), "P1", "TASK-1", {"a": 3},
                  expected_revision=original.revision)
    assert store.get(Principal("alice"), "P1", "TASK-1").data == {"a": 2}


def test_create_cannot_overwrite_and_update_cannot_create(store):
    store.put(Principal("alice"), "P1", "TASK-1", {}, expected_revision=None)
    with pytest.raises(RevisionConflict):
        store.put(Principal("alice"), "P1", "TASK-1", {}, expected_revision=None)
    with pytest.raises(RevisionConflict):
        store.put(Principal("alice"), "P1", "missing", {}, expected_revision=1)


def test_defensive_copy(store):
    data = {"details": {"tags": ["initial"]}}
    saved = store.put(Principal("alice"), "P1", "TASK-1", data, expected_revision=None)
    data["details"]["tags"].append("after")
    saved.data["details"]["tags"].append("returned")
    read = store.get(Principal("alice"), "P1", "TASK-1")
    assert read.data["details"]["tags"] == ["initial"]


def test_unknown_member_and_missing_record(store):
    with pytest.raises(AccessDenied):
        store.get(Principal("unknown"), "P1", "TASK-1")
    with pytest.raises(MissingRecord):
        store.get(Principal("alice"), "P1", "TASK-1")


def test_reject_unverified_blank_subject():
    with pytest.raises(ValueError):
        Principal(" ")
