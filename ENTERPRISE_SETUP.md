# PEIMS v0.5 — separate enterprise API setup (staging only)

**Do not connect the public Streamlit Community Cloud dashboard to an organizational database.** v0.5 supplies an API and migration source, but **does not create any database, hosting account, tenant, DNS entry, OIDC client or company integration**.

## Architecture

`Approved IdP (OIDC access token with PEIMS API audience)` → `private HTTPS ingress` → `FastAPI` → `managed PostgreSQL (TLS, backups, restricted network)`.

The public demonstration site and GitHub Pages preview are **not** part of this path. The backend trusts only signed API-audience tokens and an explicit project-member record, never a caller-supplied role.

## 1. Prepare authorized staging resources

Provision a disposable managed PostgreSQL database, TLS identity/certificates and private-network rules, a separate service runtime, a secrets manager and a supported OIDC identity provider. For production prefer a CA-verified `sslmode=verify-full`; `sslmode=require` merely encrypts traffic without full peer identity verification.

Create a dedicated API resource/audience at the IdP and configure RS256 access tokens. Restrict the JWKS endpoint to the configured HTTPS provider. No secret or token belongs in GitHub or public Streamlit settings.

## 2. Install and migrate from a trusted administrator host

```bash
python -m pip install -r requirements-api.txt
# The following values MUST be placed into the authorized secret manager:
# PEIMS_DATABASE_URL=postgresql+psycopg://<USER>:<PASS>@<HOST>:5432/peims?sslmode=verify-full&sslrootcert=/secure/path/ca.pem
# PEIMS_OIDC_ISSUER=https://<approved-provider>/
# PEIMS_OIDC_AUDIENCE=<dedicated-api-audience>
# PEIMS_OIDC_JWKS_URL=https://<approved-provider>/.../jwks
alembic upgrade head
alembic current
```

The database migration is explicit; API startup never creates or updates tables. The two migrations are `0001_initial` (v0.4) and `0002_workspace` (v0.5). **Test upgrade and downgrade only in an expendable copy, never by downgrading a real database containing business records.**

## 3. First project and first manager

Trusted CLI only, with an auditable operator label:

```bash
python -m enterprise.manage create-project --id DEMO-001 --title "Fictional Pilot Project" --currency GHS --actor "provisioner:admin"
python -m enterprise.manage grant-member --project DEMO-001 --subject "<verified-oidc-sub>" --role manager --actor "provisioner:admin"
```

Use the exact IdP-verified `sub`; do not infer identities from email. The server CLI can also `grant-member` / `revoke-member` for recovery. No self-registration is possible. A project manager may add members via authenticated `/members` endpoints after first provisioning. Manager role changes and revocations are audited and versioned.

## 4. Launch behind secured private HTTPS ingress

```bash
uvicorn enterprise.main:app --host 127.0.0.1 --port 8000
```

Health: `GET /healthz` (process only), `GET /readyz` (DB connectivity, 503 when unavailable). All `/v1/` endpoints require `Authorization: Bearer <access-token>`. Disable direct public exposure; configure ingress rate limits, request-body limits, safe forwarding headers and logging. API documentation is intentionally not exposed automatically.

## 5. Primary API routes

- `GET /v1/projects` — authorized projects and your role
- `GET|POST /v1/projects/{project_id}/activities`; `PUT .../activities/{activity_id}` — progress
- `GET|POST /v1/projects/{project_id}/rfis`; `PATCH .../rfis/{rfi_id}` — RFIs
- `GET|POST /v1/projects/{project_id}/cost-lines`; `PATCH .../cost-lines/{line_id}` — manager only
- `GET|POST /v1/projects/{project_id}/members` — manager only; `PATCH /.../members/{principal_sub}` with `expected_version` in JSON; `DELETE /.../members/{principal_sub}?expected_version=N`
- `GET|POST /v1/projects/{project_id}/action-items`; `PATCH /.../action-items/{item_id}` — persistent action register
- `GET|POST /v1/projects/{project_id}/document-records`; `PATCH /.../document-records/{doc_id}` — **metadata only**, no file upload
- `GET /v1/projects/{project_id}/workspace-summary` — action and document status counts
- `GET /v1/projects/{project_id}/audit` — manager-only, last 100 metadata events

Mutation requests use strongly validated JSON bodies; most updates require `expected_version` to detect simultaneous changes. Both the original and new records live in PostgreSQL once configured; the public Streamlit app remains session-only and separate.

## 6. Acceptance before a shared browser client

Complete `STAGING_ACCEPTANCE.md` with two signed-in test accounts, a disposable PostgreSQL instance, token expiry/revocation exercises, post-restart persistence checks, RBAC and cross-project isolation, concurrent writes, migration/rollback drills, restore-from-backup, TLS validation and security reviews.

Streamlit native OIDC sign-in does **not** automatically grant an API access token with the right audience. Use an approved server-side OAuth code exchange and secure session storage in a future frontend; never prompt users to paste bearer tokens in a public web interface.
