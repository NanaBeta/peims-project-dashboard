# Separate enterprise API setup (administrators only)

This is a staged, developer-oriented installation guide, **not** an instruction to point the existing public Streamlit Community Cloud deployment at a company database.

## 1. Provision infrastructure outside GitHub Pages/Streamlit Community Cloud

- Managed PostgreSQL with private ingress, encrypted connections, restricted database credentials, backups and monitored availability.
- OIDC identity provider (e.g. enterprise Entra ID / Auth0 / Okta) authorized by the organization. Register an **API resource/audience** and configure issuance of a signed RS256 **access token** for that resource.
- Separately hosted FastAPI backend behind HTTPS ingress, IP/rate controls and monitoring. Streamlit remains a separate frontend until identity integration and organizational approval are implemented.
- A secret manager for the database URL and OIDC values; do not commit `secrets.toml`, tokens, `.env` or production files.

## 2. Install and configure

```bash
python -m pip install -r requirements-api.txt
# Set secret values via a real environment/secret manager (not in the repository):
# PEIMS_DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/peims?sslmode=require
# PEIMS_OIDC_ISSUER=https://<provider>/
# PEIMS_OIDC_AUDIENCE=<API resource identifier>
# PEIMS_OIDC_JWKS_URL=https://<provider>/.../jwks
alembic upgrade head
```

Migrations must run **before** starting the service. The API deliberately does not auto-create tables on startup.

## 3. Explicit project/member provisioning

Use the trusted administrator's terminal and PostgreSQL role, **never browser-side commands**:

```bash
python -m enterprise.manage create-project --id DEMO-001 --title "Fictional Pilot Project" --currency GHS
python -m enterprise.manage grant-member --project DEMO-001 --subject "<verified-OIDC-sub>" --role manager
```

Use the exact verified subject (`sub`) from the identity provider's issued access token. Do not use email addresses as authority unless the identity provider explicitly guarantees identity mapping. Members are not created automatically from untrusted requests.

## 4. Launch the backend (in a secured server environment)

```bash
uvicorn enterprise.main:app --host 127.0.0.1 --port 8000
```

Ingress should terminate HTTPS and forward requests to the private backend. An unauthenticated GET to `/v1/projects` must return **401**; `/healthz` is liveness only and does not confirm database integrity or full readiness. All `/v1/...` requests require `Authorization: Bearer <API-access-token>`.

## 5. Test before integrating a UI

- Validate certificate, token issuer/audience and membership scoping using representative test accounts.
- Test that one project's engineer cannot read or edit a different project's records, and a viewer cannot change anything.
- Verify row version conflicts, cost manager-only restrictions, audit writing, rollback, backups and migration downgrades in a disposable staging database.
- Perform API abuse tests, access-log inspections, penetration testing and organizational security review.
- Only then design a frontend with a **safe access-token exchange**; do not ask operators to paste tokens into a public form.

Streamlit's native OIDC authentication is only identity verification and **not** automatically an API authorization mechanism. For API calls, a backend-compatible access token with the correct audience is required.

## Milestones

- v0.4 provides code, tests and illustrative calculations, **not production identity/DB hosting**.
- Subsequent work: staging Postgres + OIDC, operational secrets, frontend integration, RLS, enterprise import/export adapters, approved data governance.
