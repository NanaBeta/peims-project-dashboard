# PEIMS v0.8.4 — storage contract (development only)

This increment introduces `free_workspace_store.py`: a **storage-neutral API contract** for project-scoped record reads/writes, with a **test-only** in-memory reference implementation.

## Implemented

- Requires a trusted `Principal` identity for each call.
- Enforces explicit per-project viewer, engineer and manager membership.
- Uses `(project_id, record_id)` composite keys.
- Prevents lost updates with optimistic revisions.
- Copies returned and stored payloads to avoid accidental mutation.
- Tests cover permission denials, isolation, duplicate creation and stale writes.

## Not implemented yet

- Shared durable PostgreSQL storage (the test store loses all data when restarted).
- An OIDC login bridge between Streamlit and the verified subject.
- Streamlit UI connection, cloud account provisioning, migrations or backups.

**Do not inject browser-provided subject/roles into this API.** A future Postgres implementation must check membership and update revisions atomically within SQL transactions. The service remains off by default in `app.py`. No paid or free cloud resources are provisioned by these commits.

Next: implement a free-compatible PostgreSQL adapter and real-database integration tests before connecting the authenticated Streamlit UI. Do not introduce SQLite-as-durable-cloud-storage or a shared service-account permission bypass.
