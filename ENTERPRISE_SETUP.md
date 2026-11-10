# PEIMS — separate enterprise API setup (staging only)

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

The database migration is explicit; API startup never creates or updates tables. The migration chain is `0001_initial` (v0.4), `0002_workspace` (v0.5), `0003_organization_directory` (v0.6.3), and `0004_work_management` (v0.8). **Test upgrade and downgrade only in an expendable copy, never by downgrading a real database containing business records.**

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

## 7. Organization directory — v0.6.3 (backend only)

**This code is not connected to the public Streamlit demonstration.** Existing project-specific suggestions remain the only source of values in that app. An approved, authenticated enterprise frontend must later call these API endpoints with its own server-side OIDC access token.

### Isolation and opt-in policy

1. Organization provisioning is disabled by default. Configure `PEIMS_ORG_BOOTSTRAP_SUBS` with a **small, trusted, server-side** comma-separated list of verified OIDC `sub` claims to authorize `POST /v1/organizations`. Do not set this in a public Streamlit deployment, and do not infer OIDC subjects from email addresses.
2. Every new organization is isolated and the creator becomes its first admin. Admins may grant/revoke `member` and `admin` organization memberships. Project membership remains separate.
3. Every existing project remains **unlinked**, with `directory_enabled=false`. Only an existing **project manager who is also an admin of the destination organization** can link a project. Cross-organization transfers are blocked by default; they require a future explicit, audited administrative process.
4. A project manager who also belongs to the organization may enable the directory via version-checked settings. An organization's values are never available merely because two projects have similar labels.
5. Members may *propose* directory values (pending). Only organization admins can approve them. **Unreviewed, rejected or archived values are never returned** as shared suggestions. No project entries are automatically promoted.
6. Shared suggestions require valid OIDC authentication, *project membership*, *organization membership*, project opt-in, and organization/kind/status filters. The endpoint returns only approved labels (no private contract terms, rates, member details or project records).
7. Managers can switch the project back to project-only mode immediately. Organization membership revocation immediately removes access to shared suggestions on the next request.

### Routes (all `/v1/...` routes require a verified API-audience bearer token)

| Route | Authorization | Purpose |
| --- | --- | --- |
| `POST /organizations` | trusted `PEIMS_ORG_BOOTSTRAP_SUBS` | Create isolated organization and first admin |
| `GET /organizations` | authenticated | List only organizations the principal belongs to |
| `GET, POST /organizations/{org_id}/members` | organization admin | Review/provision scoped members |
| `DELETE /organizations/{org_id}/members/{sub}` | organization admin, cannot self-revoke | Revoke organization access |
| `POST /projects/{project_id}/organization-link` | project manager **and** destination organization admin | Link an unlinked project, initially disabled |
| `GET /projects/{project_id}/directory-settings` | project member | Inspect opt-in status and optimistic version |
| `PATCH /projects/{project_id}/directory-settings` | project manager; org member if enabling | Enable/disable with `expected_version` |
| `POST /organizations/{org_id}/directory` | organization member | Propose a reusable value, initial status pending |
| `GET /organizations/{org_id}/directory?status=pending` | organization admin | Review queue (or selected status) |
| `PATCH /organizations/{org_id}/directory/{entry_id}` | organization admin | Approve/reject/archive with `expected_version` |
| `GET /projects/{project_id}/directory-suggestions?kind=supplier` | project & organization member, after opt-in | Approved suggestions; project-only fallback when off |
| `GET /organizations/{org_id}/directory-audit` | organization admin | Last 100 org audit events |

Directory kinds: `contractor`, `supplier`, `discipline`, `person`, `category`, `document_type`. These are *approved lookup labels*, **not** supplier accounts, signed contracts, verified personnel identities, or company-wide visibility into project registers.

### Illustrative workflow

1. Configure bootstrap subjects; run Alembic migration `0003_organization_directory` on isolated, backed-up PostgreSQL staging after rehearsing an upgrade and rollback.
2. Org-admin creates the organization, provisions OIDC-subject members and manually proposes/approves safe company directory entries.
3. A project manager who is also org admin links the project by the organization UUID. Link is initially inactive.
4. Project manager **explicitly enables** organization suggestions with a version-checked request.
5. An authenticated project+org member retrieves approved values by `kind`; the future client merges them with the existing local/project suggestions. If not opted in, the result is `project_only` with no organization values.
6. Org admin archives an obsolete entry or revokes access; next request reflects the change.

**Not yet available:** database hosting, actual organization provisioning, authenticated Streamlit-to-API integration, organization administration UI, invitations and identity-lifecycle orchestration, PostgreSQL integration testing, rate limiting, CSRF/session policy for a browser client, or a business-verified organization onboarding workflow. Implement and test these before processing any confidential customer data.

## 8. Durable collaborative task records — v0.8 (backend only)

**Code release only.** The public Streamlit task views are **not** connected to this API and retain session-only data. Never send demo ZIP backups or real organizational records to an unapproved server.

### Storage and deployment

New revision `0004_work_management` adds four project-scoped tables for tasks, finish-to-start dependencies, time entries and comments. Run `alembic upgrade head` **after** verifying a recoverable PostgreSQL staging backup and authorized OIDC tenant. No database is automatically migrated at application startup. Rehearse failover, concurrent writers and rollback on disposable staging (not production with records).

The API continues to require `Authorization: Bearer <verified-api-access-token>`. The `sub` claim must already be a `members.principal_sub` for the requested project. Roles: `viewer` can read; `engineer` and `manager` can create/update tasks, dependencies, time entries and comments. Project managers alone can manage project membership; revoking a member assigned to work items is blocked until those tasks are reassigned. Assignment requires a member with an engineer or manager role.

### Task and collaboration endpoints

All URLs below are prefixed by `/v1/projects/{project_id}`:

| Route | Purpose |
| --- | --- |
| `GET /work-items?status=todo&limit=100&offset=0` | Project-specific task list with pagination/filtering |
| `POST /work-items` | Create task, subtask or milestone |
| `GET /work-items/{item_id}` | Fetch one project work item |
| `PATCH /work-items/{item_id}` | Update with `expected_version` (409 on conflict) |
| `GET /work-items/{item_id}/predecessors` | List finish-to-start predecessors |
| `POST /work-items/{item_id}/predecessors` | Add predecessor; cycle/self/cross-project checks |
| `DELETE /work-items/{item_id}/predecessors/{predecessor_id}` | Remove predecessor, audited |
| `GET, POST /work-items/{item_id}/time-entries` | Read/add append-only signed time records |
| `GET, POST /work-items/{item_id}/comments` | Read/add append-only plain-text comments |
| `GET /work-summary` | Live task counts and recorded project hours |

Example authenticated JSON request bodies (do not paste real access tokens into source, docs or public Streamlit controls):

```json
{
  "reference": "ENG-001",
  "title": "Review cable routing",
  "kind": "task",
  "status": "todo",
  "priority": "high",
  "assigned_sub": null,
  "start_date": "2026-11-11",
  "due_date": "2026-11-20",
  "estimate_hours": "8.00",
  "progress_pct": "0"
}
```

```json
{"expected_version":1,"status":"in_progress","progress_pct":"25"}
```

```json
{"predecessor_id":"<existing-project-work-item-uuid>"}
```

```json
{"work_date":"2026-11-11","hours":"1.50","note":"Reviewed cable schedule"}
```

```json
{"body":"Please check the revision before the review meeting."}
```

All work-item and comment content should be rendered as escaped text by a future client; a string beginning with `@` does **not** generate a notification. Status transitions are recorded in project audit metadata. Dependencies do not automatically revise the approved activity baseline or commercial cost ledger. The API has no unreviewed task deletion endpoint.

### Required integration gates

1. Run 0004 migration in a disposable PostgreSQL staging copy and verify composite foreign keys, version conflicts and concurrent dependency updates across real transactions.
2. Configure and verify IdP JWT issuer/audience/JWKS, project provisioning and signed-in engineer/manager/viewer acceptance tests.
3. Test persistence after service restart, restore of encrypted backups, audit retention, least-privilege DB credentials, app-level logs and database-level tenant safeguards.
4. Build a future **private authenticated frontend** using supported OAuth code exchange. Do **not** connect the public Streamlit app, put raw tokens into UI text inputs, or enable broad CORS without an approved threat review.
5. Prepare an explicit, validated migration path for earlier session ZIP work data. No legacy data is silently imported.


## v0.8.1: authenticated browser frontend

The separate enterprise `/console/` interface is implemented in source, **not enabled** on the public Streamlit site. It uses a confidential OIDC authorization-code + PKCE exchange, short-lived server-side login sessions, CSRF checks and the existing v0.8 project-authorization handlers. Run `0005_console_sessions` **only after PostgreSQL staging backup**. See [full staging deployment steps](ENTERPRISE_CONSOLE_v081.md). The existing direct `/v1` API continues to require API-audience bearer tokens; the console uses its own verified ID token exclusively for login and does not pass that ID token to the API as authorization.
