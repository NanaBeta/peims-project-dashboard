# PEIMS free-first deployment plan (v0.8.3 planning checkpoint)

**Non-negotiable constraint: no paid hosting, billing activation or resource provisioning without express user approval.** This file supersedes the paid Render guide as the *recommended direction*, but does not remove or deploy any existing source. The `render.yaml` blueprint is dormant, not part of the Streamlit launch.

## Verified starting point

- **Frontend:** `app.py` on Streamlit Community Cloud from `main`, currently fictional-data and per-session only.
- **Enterprise backend:** `enterprise/` contains a separately hosted FastAPI/OIDC/PostgreSQL service, not integrated with `app.py`. The passing PostgreSQL CI job is a *temporary test database*, not hosted persistence.
- **Backups today:** manual session ZIP exports, not a shared durable database.
- **Privacy:** the existing public demonstration must remain fictional. Never paste real workplace credentials or confidential project records into the demonstration.

## Free-first target

| Layer | Initial choice | Design constraint |
|---|---|---|
| Browser experience | Streamlit Community Cloud | Use existing `app.py`; respect app sleep/resource limits |
| Source and quality gate | GitHub and GitHub Actions | Keep within included free usage limits |
| Database | Optional free PostgreSQL project (e.g., Supabase Free) | Limited capacity, inactivity pausing, no guaranteed availability or backups |
| Login | Streamlit `st.login` with a separately configured OIDC provider | Verify identity; do **not** confuse login with project authorization |
| Authorization | PEIMS project memberships in database | Every read/write scoped to the authenticated principal and project |
| Secrets | Streamlit app secrets, never source control | Never expose DB URLs/tokens to the browser, GitHub logs or user interface |
| Export | Project-scoped manual exports and independently tested restores | Free-tier database is not a disaster-recovery guarantee |

This is a development/pilot architecture, not an approved production system. Streamlit Community Cloud does **not** host the existing FastAPI HTTP API or provide a continuously running Postgres server. Simply setting `PEIMS_DATABASE_URL` on Streamlit is **not** an integration. Reusing enterprise business logic in-process requires a purpose-built authenticated adapter with authorization, transactions and tested failure behavior.

## Implementation gates (in order)

1. **Protect current app:** keep demo default session-only; establish tests that its Python requirements do not silently pull in paid backend services.
2. **Introduce a persistence interface:** project-scoped read/write operations with explicit configured/demo modes; never share state implicitly between Streamlit sessions.
3. **Add authentication and project membership checks:** no persistence-backed UI route before an allowlisted authenticated account has verified membership. No development bypass in Cloud.
4. **Integrate free Postgres:** create schema through reviewed migrations, require TLS and secret-only connection configuration; test reconnect, paused service, concurrent edits, unauthorized projects and reloaded sessions.
5. **Add reliable project export/import and recovery verification:** no claims of automatic managed backups on free hosting.
6. **Run private pilot with fictional data:** two independent identities, task creation across restart, no cross-project leakage, and observed limits. Roll out only after verification.

## Explicit exclusions until separately approved

- No Render provisioning, paid web service, paid PostgreSQL, trial that automatically bills, or payment-card requirement.
- No automatic migration of the Streamlit sample records into live enterprise records.
- No storing a shared admin API key in session state or client-side browser data.
- No promises of 24/7 uptime or enterprise-grade security on free tiers.
- No real mining/company/HSE/finance data in the free pilot.

## Current status

The free-first approach is **planned, not yet deployed**. The present hosted Streamlit app remains a session-only fictional demonstration. The next engineering milestone is the persistence interface and its tested authentication boundary, *not* infrastructure provisioning.

## Documentation

- https://docs.streamlit.io/deploy/streamlit-community-cloud
- https://docs.streamlit.io/develop/concepts/connections/authentication
- https://supabase.com/docs/guides/platform/free-project-pausing
- https://supabase.com/pricing
