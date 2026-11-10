## NEW v0.8.1 — Authenticated enterprise console (source release; not deployed)

A private, same-origin `/console/` web UI now connects to the persistent v0.8 work-management API through server-side OIDC sessions. Project-specific Home, task board, list, planned timeline, calendar, task updates, comments and signed time records are supported. No browser access tokens, no automatic live data or migration from the public Streamlit demo. See [release notes](RELEASE_NOTES_v0.8.1.md) and [deployment guide](ENTERPRISE_CONSOLE_v081.md).

## v0.8 — Persistent task and collaboration API foundation (separate service)

The enterprise FastAPI source now provides durable project-scoped work items, version-checked updates, dependency links, signed time logs, comments, and audited project summaries, plus migration `0004_work_management`. All API routes require OIDC access tokens and explicit project membership. This implementation is **not deployed or connected** to the public Streamlit demonstration, which continues to store changes in the current browser session. See [v0.8 release notes](RELEASE_NOTES_v0.8.md) and [staging setup](ENTERPRISE_SETUP.md).

## NEW — Gantt timeline (v0.6.4)

**Home** now includes an at-a-glance project Gantt, **Command centre** includes the full schedule picture, and **Planning & schedule → Gantt** provides owner/status filters, zoom, activity detail navigation and CSV export. The bars show planned date windows and reported percent completion; actual work dates and forecasts are **not** inferred. [Details](RELEASE_NOTES_v0.6.4.md).

# NEW — Smart entry suggestions (v0.6.2)

Add entries from **Spreadsheets & BI → Worksheet grid → ＋ Add an entry with suggestions**. Owners, disciplines, categories, suppliers and related fields suggest previously used values from the selected project, and free-text fields also permit new labels. The grid supports suggestion dropdowns with an opt-out to type freely. See [release notes](RELEASE_NOTES_v0.6.2.md).

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

### Spreadsheet Studio: adding new records (v0.6.1)

Open **Spreadsheets & BI → Worksheet grid**, choose a supported worksheet and click the **+ Add row** control at the bottom of the grid. Add a unique ID (for example `ACTION-NEW-001`) and the required fields, then select **Validate & apply worksheet changes**. The selected project is set automatically. Existing IDs cannot be changed or deleted in the sheet.

Adding an activity also creates its matching cost-ledger row (zero actual/committed costs); to enter expenses, open **Cost ledger** afterwards. Standalone cost-row creation is disabled because PEIMS currently requires one cost row per activity. You can also append rows to an exported Excel workbook and import the selected sheet through **Excel exchange**. All changes remain session-only until backed up.

## v0.6.3 — Organization directories (backend foundation, not live Streamlit)

PEIMS now contains a **secure-by-default hybrid-suggestion backend**: project-local values remain the default, while an organization can curate and approve reusable values for its own authorized projects. An organization admin must approve shared values; a project manager explicitly links and opts the project in; a user must be a member of both the project and the organization before the API returns shared suggestions. Existing projects remain unlinked and off after migration. No automatic harvesting of project names/owners/suppliers into the organization directory occurs.

The public Streamlit demo has no enterprise token, database or organization account. It continues to suggest values **only from the selected demo project**, with global application presets where applicable. Real shared suggestions will require deploying the separate enterprise service and building an OIDC-authenticated interface. See [ENTERPRISE_SETUP.md](ENTERPRISE_SETUP.md) and [RELEASE_NOTES_v0.6.3.md](RELEASE_NOTES_v0.6.3.md).

## v0.7 — Tasks & work management

Open **Home → Manage tasks**, or **Tasks & work management** in the sidebar. The same session task records appear in a Kanban-style Board, List, Timeline, Calendar, Dependencies & CPM, Workload and Time & rules. You can create a task, subtask or milestone, edit statuses and owners, add finish-to-start links, enter resource capacity, log hours, and set simple status-to-priority rules. Use the **Backup / restore project work records** section to export session edits in a project-scoped ZIP archive. The work-management timeline does not silently modify the separate approved activity baseline Gantt or cost ledger. This remains a fictional, session-only demo. Details: [release notes](RELEASE_NOTES_v0.7.md) and [15-feature roadmap](FEATURE_ROADMAP_15.md).

## v0.8.2 — Enterprise staging deployment kit (not a deployed environment)

The repository now provides a manually triggered Render staging Blueprint (`render.yaml`), a guarded `enterprise.staging_runtime` entrypoint, and a remote smoke checker. **No hosting account, PostgreSQL instance or OIDC tenant is created by merging code into GitHub.** The public Streamlit demo remains session-only. See [STAGING_DEPLOY_RENDER.md](STAGING_DEPLOY_RENDER.md) and [v0.8.2 release notes](RELEASE_NOTES_v0.8.2.md) before provisioning any paid staging resources.
