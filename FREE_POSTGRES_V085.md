# PEIMS v0.8.5 — free-compatible PostgreSQL adapter

This PR adds `free_workspace_postgres.py`, implementing the v0.8.4 workspace contract using SQLAlchemy and PostgreSQL. It is **not connected** to the existing Streamlit app and does **not** provision or require a paid hosting account.

## Security and behavior

- Project membership is checked on every request in the same DB transaction as the record operation.
- Viewer has read-only access; engineer and manager can write their own project records.
- A composite `(project_id, record_id)` key isolates record namespaces.
- PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` and conditional `UPDATE ... WHERE revision=...` prevent overwrites, including concurrent writes.
- No client-supplied role or authentication claim is accepted by the storage interface. Calling code must construct `Principal` only after verified sign-in.
- JSON data is stored as JSONB, rejecting invalid numeric NaN/Infinity.
- SQL schema name is validated before interpolation; all user identifiers and JSON values use bound SQL parameters.

## CI verification

`scripts/free_postgres_acceptance.py` creates isolated tables **only on the disposable CI PostgreSQL instance** when `PEIMS_EPHEMERAL_POSTGRES_TEST=yes` and the URL points to the local `peims_stage` test database. It tests persistence through separate store instances, permissions, record ownership scoping, stale writes and two simultaneous writes. It removes its test schema after completion.

## Remaining before shared Streamlit data

1. Create reviewed schema migration integrated into the *existing* enterprise database schema, rather than the isolated CI schema.
2. Integrate authenticated Streamlit sign-in and map verified user identities into existing project memberships; never rely on a name or project role typed into the UI.
3. Configure a free-tier PostgreSQL database over TLS and store its URL only in Streamlit secrets. Free plans can pause and lack backup guarantees; test explicit export/restore.
4. Test read/write recovery on a fresh Streamlit session, account revocation, unauthorized reads and network outages.
5. Retain demo-only mode until all security tests pass. No confidential company records are allowed in this free pilot.

The existing `render.yaml` remains unused. No hosting account or financial commitment has been made.
