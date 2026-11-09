# PEIMS v0.4 · Architecture and project-control upgrade

## In the Streamlit demo

- Added dependency-based finish-to-start schedule simulation, including earliest start/finish, total float, critical path and projected network finish based on static baseline constraints.
- Added a transparent CPI-continuation estimate at completion, estimate to complete and variance at completion with assumptions beside the numbers.
- Preserved the existing v0.3 functionality and the public GitHub Pages preview.

## Enterprise backend source (not deployed)

- FastAPI with JWT bearer validation through a configured HTTPS JWKS, explicit issuer and API audience.
- PostgreSQL 3 driver and SQLAlchemy models with initial Alembic migration.
- Project membership roles (viewer, engineer, manager); managers have exclusive access to cost lines and audit trail.
- Project-scoped endpoints to list and create activities and RFIs, update activity progress and RFI statuses, and create and update cost lines.
- Integer row versions for 409 conflict detection on edits; database transactions write metadata audit events together with changes.
- No self-service signup, hardcoded login, token minting endpoints or public database connection.

## Known limitations

- Streamlit's public demo is still session-only and cannot be used for confidential project records.
- The enterprise API, database and identity provider are separate code/future infrastructure; no multiuser production service has been deployed.
- PostgreSQL migration and a real identity provider have not yet been end-to-end tested against live infrastructure.
- The audit events are application-maintained metadata, not an immutable or regulatory-grade audit ledger. A PostgreSQL database owner can modify records.
- CPM lacks complex lag types, work shifts, progress-driven forecasting and resource-constrained scheduling; EAC is a simplistic scenario calculation.
- Approval workflow and actual connection to SAP, P6, Aconex, SharePoint or Newmont are not included.
