# Deploying the PEIMS v0.8.1 enterprise console

**Separate private service:** The existing public Streamlit demo is not the enterprise console. Do not place a production token, client secret, or PostgreSQL credential in the public app's environment. Production onboarding requires organizational authorization, an OIDC tenant, a managed database, TLS termination, monitoring, and staging approval.

## Architecture

```text
Browser ──HTTPS──> PEIMS FastAPI, same origin `/console/`
  │               ├── Static JS/CSS/HTML (no tokens in browser storage)
  │               ├── OIDC authorization-code + PKCE exchange on server
  │               ├── HttpOnly session cookie → hashed PostgreSQL session
  │               └── `/console/api/*` → v0.8 service handlers
  │                                      └── project role checks → PostgreSQL
  └────────── redirects to authorized identity provider for sign-in
```

A verified OIDC ID token is used solely to establish the browser login session. Existing direct `/v1/*` API endpoints independently continue to verify **API-audience access tokens**, and cannot be accessed using just a browser session cookie. Console routes dispatch the same business logic internally with the verified session identity. The browser never receives an access or ID token.

## Provider registration (confidential server-side web client)

Register a **separate confidential web client** at your approved OpenID Connect provider. Enable authorization code grant with PKCE (S256) and `openid profile` scopes, with the exact callback URL:

`https://<your-private-PEIMS-host>/console/callback`

The ID token must be signed with RS256 and contain `iss`, `aud`, `sub`, `iat`, `exp`, `nonce`, with `aud` equal to the **console client ID**. Your provider must support server-to-server authorization-code exchange with a client secret. If these requirements are not supported, adapt and re-review authentication; do not remove the checks.

## Required private environment variables

| Variable | Description |
| --- | --- |
| `PEIMS_DATABASE_URL` | Encrypted managed PostgreSQL DSN (`postgresql+psycopg://...?...sslmode=verify-full` recommended) |
| `PEIMS_OIDC_ISSUER` | Exact issuer of verified identity tokens (including trailing slash if the provider uses one) |
| `PEIMS_OIDC_JWKS_URL` | Verified HTTPS signing key endpoint |
| `PEIMS_OIDC_AUDIENCE` | API audience for direct bearer-token `/v1` clients (separate from browser client ID) |
| `PEIMS_CONSOLE_ORIGIN` | HTTPS origin only (e.g. `https://peims.internal.example`), without path or trailing slash |
| `PEIMS_CONSOLE_AUTHORIZE_URL` | Full HTTPS OIDC authorization endpoint |
| `PEIMS_CONSOLE_TOKEN_URL` | Full HTTPS token endpoint reachable only from trusted backend environment |
| `PEIMS_CONSOLE_CLIENT_ID` | Confidential web-client ID from the approved OIDC provider |
| `PEIMS_CONSOLE_CLIENT_SECRET` | Confidential web-client secret, server-side only (never browser JS) |
| `PEIMS_CONSOLE_COOKIE_KEY` | Fernet key used to encrypt temporary OAuth flow cookies and derive CSRF protection |

Generate a random Fernet key on a trusted computer:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store it in an access-controlled secret manager with stable availability across replicas. **Do not share or paste an actual key into ChatGPT or commit it to GitHub.** Rotate during a controlled deployment (existing browser sessions and login flows will need to reauthenticate). Set cookie keys only in production secrets, not `.env.example` or public Streamlit settings.

## Staging procedure

1. Prepare isolated managed PostgreSQL with TLS, backup/restore verification, least-privilege credentials, and network restrictions. Configure an approved OIDC tenant and two test identities; verify known stable `sub` values.
2. Review migrations `0001`–`0005`, take a recoverable backup, and run `alembic upgrade head` in **staging**. No automatic schema changes happen on startup.
3. Provision **fictional** projects and memberships using the trusted `python -m enterprise.manage create-project` / `grant-member` commands, using exact OIDC `sub` claims. Assign at least one `manager` and `engineer`; optionally a `viewer`.
4. Deploy `uvicorn enterprise.main:app --host 127.0.0.1 --port 8000` behind TLS termination and an approved reverse proxy. Set HSTS, request/connection rate limits, request-body caps, trusted proxy headers, secure logs, and same-origin routing at the edge. Do not expose the database or provisioning CLI.
5. Open `https://<your-private-PEIMS-host>/console/`. Sign in through the provider. Verify callback state/nonce, secure cookies, and access only to authorized projects. The public Streamlit demo remains separately hosted and unchanged.
6. Exercise board, table, planned timeline, calendar, task create/edit, comments, time entries, predecessors and version conflict handling with two accounts. Confirm shared records survive service and browser restarts.
7. Confirm a viewer cannot write, removed project memberships immediately lose project access, a foreign project remains a 404, cookies cannot be used as `/v1` bearer authorization, and CSRF/origin checks fail closed.
8. Test token and cookie expiry, disabled OIDC users, backup restoration, migration rollback strategy, concurrent task and dependency editing, reverse-proxy failure modes and operational monitoring. Enable real production data only after formal security approval.

## Operational notes

- Session handles are stored **hashed** in `browser_sessions`; expire no later than the verified ID token's expiry and one hour from login. The login verification flow uses short-lived encrypted cookies (5 minutes); login cookies require Secure + HttpOnly + SameSite=Lax, exact `__Host-` prefix semantics and HTTPS.
- Logging out deletes the session database record. Existing browser sessions are invalid after OIDC sign-out only when they expire or the PEIMS session is explicitly revoked; integrate centralized logout/back-channel revocation before high-security enterprise production use.
- The v0.8 API persists tasks, dependencies, signed time entries, comments and audit metadata. The UI uses paginated data, 100 records per page; views are per-page, not a substitute for portfolio-wide BI or an approved scheduling baseline.
- No external SDK, CDN or browser token storage is required for the console. JS uses `textContent` rather than inserting untrusted HTML. The app sets a restrictive CSP, anti-frame and no-sniff headers; the edge must enforce TLS/HSTS.
- The project-oriented organization directory remains opt-in and API-only until separately integrated and tested.

## Troubleshooting

- **503 on `/console/login`:** Missing or invalid HTTPS issuer, provider endpoints, origin, client credentials or Fernet key.
- **401 after callback:** State/nonce mismatch, expired flow, wrong OIDC issuer/audience/signature, or failed provider token exchange. Inspect anonymized server logs, never token contents.
- **401 on `/console/api/session`:** Missing, forged, expired or revoked browser session cookie. Sign in again.
- **403 on task edits:** Viewer role or invalid CSRF/origin. Do not bypass; check provider login, project memberships and browser origin.
- **404 on another project:** Intentional project isolation.
- **409 on edit:** Another user changed the record. Reload and review before saving again.

See `RELEASE_NOTES_v0.8.1.md` and `STAGING_ACCEPTANCE.md`.
