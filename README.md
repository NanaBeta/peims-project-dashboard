# PEIMS — Project Engineering Intelligence & Management System

**Version 0.4: prototype with a public sample-data dashboard and a separate enterprise API foundation.**

PEIMS is an independent fictional engineering portfolio prototype, **not a Newmont system**. No company approval, enterprise integration, operational protection function, or data access is implied.

## Choose what to run

| Component | Location | What works now | Limits |
|---|---|---|---|
| Streamlit demonstrator | `app.py` | Existing v0.3 workflows + dependency-constrained schedule illustration and CPI cost forecast | Public demo has no login, database or inter-user persistence; only fictional records |
| Static GitHub Pages preview | `index.html` | Earlier read-only sample dashboard | Frozen preview; does not show new v0.4 modules |
| FastAPI enterprise foundation | `enterprise/main.py` | OIDC JWT authentication, project membership roles, PostgreSQL schema/migration, activity/RFI/cost endpoints, optimistic versioning, audit events | Requires a separately provisioned PostgreSQL database, identity provider, TLS and service hosting; **NOT** running as part of Streamlit |

## New in v0.4

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
enterprise/models.py      Database schema
enterprise/auth.py        Verifies OIDC access tokens
enterprise/database.py    PostgreSQL-only DB configuration
enterprise/manage.py      Trusted terminal-only provisioning
enterprise/migrations/    Alembic schema version 0001
alembic.ini               Database migration entrypoint
requirements-api.txt      Additional enterprise service dependencies
ENTERPRISE_SETUP.md       Setup and verification instructions
SECURITY.md               Threat model, guardrails and limitations
tests/                    Local, CI and API security tests
```
