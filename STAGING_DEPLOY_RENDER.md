# PEIMS Enterprise — Render staging deployment guide (v0.8.2)

**Status: provision-ready source, not a running deployed system.** Keep `peims-project-dashboard-*.streamlit.app` entirely separate. Use **fictional** projects and consenting test accounts only. Never put database URLs, OIDC secrets, passwords or real company records into GitHub or chat.

## What the repository now provides

`render.yaml` defines an isolated paid Render web service (`peims-enterprise-staging`) and a managed PostgreSQL database in the same Frankfurt region. Automatic deployments are **off**. Postgres external inbound connections are disabled. The web service starts only after strict configuration and migration checks; it **does not** automatically modify schema or use demo-auth shortcuts.

The adapter in `enterprise/staging_runtime.py` converts Render's **internal** PostgreSQL URL into the required SQLAlchemy `postgresql+psycopg://` URL with `sslmode=require`. Render's internal PostgreSQL TLS uses self-signed certificates, so `verify-full` is not available on that connection; this adapter is only for Render internal staging, not a generic cloud database TLS policy. Database credentials never appear in the source or diagnostic messages.

## Before creating resources

1. Review Render's **paid web and database plan charges**, backups/retention and operating terms. Choose an authorized workspace. Do not deploy in an employer's account without approval.
2. Connect **Render** to ChatGPT (optional for assisted provisioning) or connect your GitHub repository to Render through [Render Dashboard](https://dashboard.render.com/). The user must explicitly approve provisioning and any charges.
3. Register an **isolated staging OIDC confidential web application** with a supported provider. It must issue RS256-signed OIDC ID tokens and support authorization code + PKCE, nonce and a client secret. Configure the exact callback `https://YOUR-STAGING-HOST/console/callback` once the Render host is known.
4. Prepare two to three test identities (manager, engineer and optionally viewer), without granting any organization data access. **Never use real company SSO credentials or sensitive project data without approval.**

## Deploy resources (after account connection and approval)

1. Use Render **Blueprints → New Blueprint instance**, pointing to this repository's `render.yaml`. Review resources and billing before confirming creation. The plan explicitly disables automatic deploys.
2. Set Render private environment values for each required `sync: false` field:

   `PEIMS_CONSOLE_ORIGIN` — exact `https://...onrender.com` or approved custom HTTPS origin; no path.

   `PEIMS_OIDC_ISSUER`, `PEIMS_OIDC_AUDIENCE`, `PEIMS_OIDC_JWKS_URL`, `PEIMS_CONSOLE_AUTHORIZE_URL`, `PEIMS_CONSOLE_TOKEN_URL`, `PEIMS_CONSOLE_CLIENT_ID`, `PEIMS_CONSOLE_CLIENT_SECRET`, `PEIMS_CONSOLE_COOKIE_KEY`.

   The secret must be at least 16 characters. Generate the cookie key on a trusted local machine with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Store the key **only** in Render's secret settings. If Render assigns a random suffix to the service hostname, update `PEIMS_CONSOLE_ORIGIN` and the IdP callback exactly.
3. Wait for database provisioning. **The first web service run is deliberately blocked until migrations have been applied.** This is intentional; it prevents a partially configured service from serving authenticated traffic.
4. From an authorized private Render Shell/job with the same service environment (including the internal DB binding), take or verify a **recoverable staging backup**, then run:

   `python -m enterprise.staging_runtime migrate --acknowledge-staging-backup`

   This explicit operation upgrades Alembic to revision `0005_console_sessions`; it does not load demonstration data. Do **not** point it at a pre-existing production database. If the Render shell cannot run before first deploy, provision and migrate with an approved one-off job in the same Render private network before enabling the service. **Do not weaken the startup checks.**
5. Manually deploy or redeploy the web service. It uses `python -m enterprise.staging_runtime serve`, checks all settings, requires migration revision `0005_console_sessions`, and binds to Render's provided `PORT` behind HTTPS.
6. Open `/healthz` (process liveness) and `/readyz` (DB connectivity), then use a trusted terminal to run `python scripts/staging_smoke.py --origin https://YOUR-STAGING-HOST`. The smoke test requires unauthorized access to both `/v1/projects` and `/console/api/session` to return 401.
7. Provision a fictional pilot and verified OIDC subjects using `enterprise.manage`:

   `python -m enterprise.manage create-project --id PILOT-001 --title "Fictional Test Project" --currency GHS --actor "staging:operator"`

   `python -m enterprise.manage grant-member --project PILOT-001 --subject "OIDC-SUB-OF-MANAGER" --role manager --actor "staging:operator"`

   Repeat the membership command for your engineer and viewer test identities using their **verified** `sub` values. The CLI must be run in a trusted shell, never as a web route.
8. Visit `https://YOUR-STAGING-HOST/console/`, sign in with the test account and test task creation, edits, comments, time logs, cross-project denials, stale version conflicts, logout and restart persistence. Record signed-off results in `STAGING_ACCEPTANCE.md`.

## Security and operating gates

- This is a **staging** web endpoint protected by OIDC/project membership, not a publicly shared production project portal. No preloaded test users, hardcoded tokens or bypasses.
- Review secure HTTPS routing, HSTS and proxy configuration, request limits/rate limiting, OWASP tests, backups with restored-copy evidence, database access logging, dependency alerts, IdP logout and revocation integration, and documented retention. Render's paid plan alone does **not** establish compliance.
- Render `ipAllowList: []` restricts **external database** connections; it does not block the HTTPS web endpoint. Place the web service behind approved access controls as your risk policy requires.
- Migrating before every deploy is **not automatic**. Schema changes must be reviewed and backed up, then executed with explicit authorization. `autoDeployTrigger: off` prevents automatic service rollouts from each GitHub push.
- All application data remains unavailable until the database, OIDC client and first memberships are actually provisioned. The Streamlit public demo remains session-based.

## Deployment acceptance state

| Gate | Status |
|---|---|
| GitHub implementation + offline deployment checks | Verified in CI on release |
| Render account/workspace connected | Not yet confirmed |
| Managed PostgreSQL created and migrated | Not yet done |
| OIDC web client registered with exact callback | Not yet done |
| Private secrets set in hosting service | Not yet done |
| Two independent test logins, persistence, restores | Not yet done |
| Real organization data approved | **Not authorized** |

**Do not mark staging live or production ready until those acceptance rows are independently verified.**
