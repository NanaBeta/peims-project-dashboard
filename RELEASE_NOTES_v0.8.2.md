# PEIMS v0.8.2 — Enterprise staging deployment kit

This release prepares the separate v0.8.1 FastAPI console for controlled **Render staging**. It does **not** create a database, deploy a new website, register an identity application, or authorize confidential business data.

## Included

- `render.yaml`: manual deployment only, isolated paid staging web service and Postgres, Frankfurt co-location, external Postgres access disabled, `/readyz` health check, all identity secrets supplied privately.
- `enterprise/staging_runtime.py`: Render internal Postgres URL normalization to SQLAlchemy psycopg with mandatory TLS; strict non-placeholder OIDC and encryption-key checks; requires exact migration head; no automatic migrations at service start.
- Explicit operator-only migration command with an acknowledged staging backup: `python -m enterprise.staging_runtime migrate --acknowledge-staging-backup`.
- `scripts/staging_smoke.py`: unauthenticated HTTPS boundary checks (liveness, DB readiness, static console and forbidden unauthorized API calls).
- `tests/test_staging_runtime.py`: offline checks for TLS, secret requirements, migration version, YAML guardrails, and origin safety.
- `STAGING_DEPLOY_RENDER.md`: provisioning, sign-in setup, multi-account acceptance and shared data safety checklist.

## Release boundaries

No public Streamlit behavior changes. The organization directory stays opt-in. The new staging template includes paid resource types, and applying it may create costs; verify account ownership and pricing beforehand. A running staging service requires independently provisioned Render and OIDC accounts, explicit database migration, verified memberships, and a security review. Without these, startup fails closed.

All code paths are for a *fictional staging pilot*. Inbound HTTPS web access does not mean production confidentiality or compliance, and there is no certification claim.
