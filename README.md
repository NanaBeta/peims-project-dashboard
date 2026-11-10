## NEW — Spreadsheet Studio (v0.6)

From **Home → Open spreadsheets**, explore/edit project worksheets, exchange validated Excel `.xlsx` workbooks, and build grouped analytical views. See [Feature matrix](FEATURE_MATRIX_v0.6.md) and [release notes](RELEASE_NOTES_v0.6.md).

This is a session-only demonstration with no company integration or persistent database.

# PEIMS v0.5.5 — Guided Workspaces

The **new Home page** is the default start screen. Select **Manage schedule**, **Review costs**, **Track deliveries**, **Resolve issues**, **Open documents**, or **Prepare a report** to enter a focused workspace. Select **Analysis** inside workspaces for full charts. The sidebar and the `← Home` button provide navigation.

This is a **fictional demonstration**: changes are session-specific, not shared or saved in a live enterprise database. The enterprise API source remains separate and is not connected to this public Streamlit frontend.

The Light/Dark/System theme remains available from Streamlit Settings → Appearance.

## Test

Run `pytest tests/ -q` and `python -m compileall -q app.py ui_shell.py experience.py`. GitHub CI installs Streamlit and executes the AppTest flows.

---

## New in v0.5.3 — Light and Dark appearance

The app supports two native Streamlit visual themes. Use **⋮ → Settings → Appearance** to select **System**, **Light** or **Dark**; see [UI_GUIDE.md](UI_GUIDE.md) and [release notes](RELEASE_NOTES_v0.5.3.md). The old fixed dark-only CSS has been replaced with palette-aware custom components and chart styling.

# PEIMS — Project Engineering Intelligence & Management System

**Version 0.5.2: professional UI refresh for the sample-data dashboard; persistent enterprise API foundation remains separate and undeployed.**

PEIMS is an independent fictional engineering portfolio prototype, **not a Newmont system**. No company approval, enterprise integration, operational protection function, or data access is implied.

## Choose what to run

| Component | Location | What works now | Limits |
|---|---|---|---|
| Streamlit demonstrator | `app.py` | Existing v0.3 workflows + v0.4 dependency-constrained schedule illustration and CPI cost forecast | Public demo has no login, database or inter-user persistence; only fictional records |
| Static GitHub Pages preview | `index.html` | Earlier read-only sample dashboard | Frozen preview; does not show new v0.4 modules |
| FastAPI enterprise foundation | `enterprise/main.py` | OIDC JWT authentication, project membership administration, PostgreSQL migrations, persistent activity/RFI/cost/action/document registers, optimistic versioning, audit events | Requires a separately provisioned PostgreSQL database, identity provider, TLS and service hosting; **NOT** running as part of Streamlit |

## New in v0.5

- **Persistent workspace endpoints:** new PostgreSQL-backed actions and engineering document metadata registers, with project-specific access and concurrent-edit checks.
- **Multiuser membership administration:** manager-only add/list/change/revoke endpoints with versioned updates, own-account protections and change audit metadata.
- **Operational readiness:** separate database readiness endpoint, enhanced trusted provisioning CLI, migration `0002_workspace`, and disposable-migration tests.
- **Still isolated from the public app:** the existing Streamlit front end remains session-only; the authenticated API requires approved Postgres/IdP/hosting and is not yet a live multiuser web application.

See [RELEASE_NOTES_v0.5.md](RELEASE_NOTES_v0.5.md), [STAGING_ACCEPTANCE.md](STAGING_ACCEPTANCE.md) and [ENTERPRISE_SETUP.md](ENTERPRISE_SETUP.md).

## Previously added in v0.4

- **Limited critical-path analysis:** finish-to-start links, non-negative whole-day lags, baseline not-before starts, cycle detection, earliest dates, total float and critical activities. The calculations are **not** a Primavera P6 replacement, do not respect work calendars or resources and do not reschedule from measured construction progress.
- **Cost-at-completion scenario:** CPI continuation EAC, ETC, and VAC. Unspent commitments are reported separately from actual costs; calculations require approved baselines and project controls review.
- **Separate enterprise API source:** SQLAlchemy models, versioned Alembic migration, PostgreSQL-only runtime configuration, OIDC JWT issuer/audience/signature verification, viewer/engineer/manager membership checks, project-scoped rows, event recording and concurrent-edit protection.
- **Secure-by-default boundary:** the public Streamlit application does **not** connect to a new database or expose an API token; secrets and deployment credentials are not included.

Existing v0.3 dashboard features remain: project overview, schedules, cost controls, procurement, risk/actions, reporting, data studio, editable contractor/RFI/document metadata registers and session ZIP backups.

## Run the public fictional-data dashboard

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Local or GitHub Pages preview: open `index.html` in a browser. The preview is not the Streamlit app.

## Test

```bash
python -m pip install -r requirements.txt -r requirements-api.txt pytest
python -m pytest tests/ -q
python -m compileall -q app.py analytics.py workflow.py project_controls.py enterprise/
node scripts/test_preview.js
```

The Streamlit integration tests need Streamlit installed. GitHub Actions installs both sets of dependencies.

## Deploy the enterprise API (separate infrastructure)

See [ENTERPRISE_SETUP.md](ENTERPRISE_SETUP.md) and [SECURITY.md](SECURITY.md). Required: PostgreSQL with encrypted connections, verified OAuth/OIDC access tokens intended for the API, server-side provisioning of project members, a secrets manager, HTTPS ingress, backups and a formal deployment/security review. None of these are configured by GitHub or Streamlit Community Cloud automatically.

**Never enter actual Newmont records into the public demo.** Do not enable an unreviewed enterprise API for mining, HSE, procurement or financial decisions.

## Source layout

```text
app.py                    Streamlit sample dashboard
analytics.py              Existing validation and earned value calculations
workflow.py               Existing session workflow registers
project_controls.py       v0.4 limited CPM and CPI forecast methods
data/dependencies.csv     Fictional finish-to-start scheduling links
enterprise/main.py        REST API application (not a Streamlit service)
enterprise/workspace.py   v0.5 membership, action and document endpoints
enterprise/permissions.py Shared project-scoped permissions and audit metadata
enterprise/models.py      Database schema
enterprise/auth.py        Verifies OIDC access tokens
enterprise/database.py    PostgreSQL-only DB configuration
enterprise/manage.py      Trusted terminal-only provisioning
enterprise/migrations/    Alembic schema versions 0001 and 0002
alembic.ini               Database migration entrypoint
requirements-api.txt      Additional enterprise service dependencies
ENTERPRISE_SETUP.md       Setup and verification instructions
SECURITY.md               Threat model, guardrails and limitations
STAGING_ACCEPTANCE.md     PostgreSQL/identity/security staging gate
tests/                    Local, CI and API security tests
```


## Professional analytics upgrade (v0.5.1)

The public demonstration now includes: (1) recorded progress S-curves, (2) activity-level baseline/actual dumbbells, (3) dependency-modelled criticality timeline, (4) earned-value/actual-cost variance waterfall, (5) work-package schedule-versus-cost exposure scatter, (6) PO date/value delivery map, and (7) a probability × impact risk severity matrix. A dedicated **Analytics Studio** adds owner drill-down and work-package detail. All figures use coherent severity colors, hover context, and explicit metric assumptions.

The weekly S-curve contains historical reported points **only**; no future forecasts are invented. The risk matrix uses color for P×I score and text for the observed open-risk count (they are not interchangeable). The cost waterfall is a reconciliation of EV and AC, not a financial cash-flow projection. The prototype remains demo-only with synthetic records and no company connection.


## Professional interface refresh (v0.5.2)

The public Streamlit front end now uses sidebar workspace navigation instead of nine compressed horizontal tabs. A structured project header, exception indicators, more consistent KPIs/chart containers, a compact-view preference, and responsive styles improve review and navigation. Select a section in the sidebar to render its content. This is a **presentation update**; analytical methods, data sources, and the enterprise API are unchanged. See [UI_GUIDE.md](UI_GUIDE.md) and [RELEASE_NOTES_v0.5.2.md](RELEASE_NOTES_v0.5.2.md).

## v0.5.4 interface polish

The project header now distinguishes actual and baseline with a target marker, while the Command centre has responsive Quick Access navigation and the sidebar keeps less-used settings collapsed. See `RELEASE_NOTES_v0.5.4.md` and `UI_GUIDE.md`.
