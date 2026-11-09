# PEIMS — Project Engineering Intelligence & Management System

**Version 0.2 · Cloud-ready source package · Fictional data only**

PEIMS is an independent engineering portfolio prototype. It is **not associated with Newmont**, not connected to operational systems, and not an approved system for safety, planning, procurement, or financial decisions.

## Choose the version

| Mode | File / deployment platform | What it offers |
|---|---|---|
| Read-only interactive demo | `index.html` on any modern browser or GitHub Pages | Six dashboard views, two projects, project switcher, Markdown report downloads; no login or server |
| Editable application | `app.py` on Streamlit Community Cloud | Seven tabs, analytics, charts, register downloads, session-only CSV replacement, report downloads |

The static preview **does not** accept CSV uploads, persist changes, or execute the Python calculation engine at runtime. Its synthetic datasets were generated from the Python calculations and checked for consistency in tests.

## Modules

1. Command centre: progress, alerts and management attention
2. Scheduling: activity progress, timeline and illustrative schedule index
3. Cost control: EV, PV, AC, CPI and cost variances
4. Procurement: expected deliveries and late / critical orders
5. Risk and actions: 5x5 matrix and follow-up register
6. Weekly report: transparent rule-based Markdown / text export
7. Data studio (Streamlit only): CSV templates, validation, temporary replacement and reset

All prompts and warnings are deterministic rules, **not predictive AI**. No third-party AI services or company integrations are present.

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md) for verified GitHub Pages and Streamlit Community Cloud steps, including guidance for a phone-only workflow.

**To run locally (Python 3.11–3.12 recommended):**

```bash
pip install -r requirements.txt
streamlit run app.py
```

**Test:**

```bash
pip install pytest
python -m pytest tests -q
node scripts/test_preview.js
```

The GitHub Actions workflow at `.github/workflows/ci.yml` runs automated checks on each push. AppTest integration checks require Streamlit to be installed; without it they are skipped.

## Controls and limitations

- Only demonstration data is supplied; no real mine, person, contractor, or business financial records.
- Uploaded CSVs are held in session state, not saved in a production database; refresh/reset can discard changes.
- A 10 MB upload limit is configured for the demo; application use is restricted to approved sample records.
- The planned schedule is time-linear by activity; this does **not** replicate Primavera P6 critical-path logic, approved progress measurement, or resource-loaded baselines.
- There are no roles, authentication, audit history, data backups, formal approvals, predictive models, or enterprise interfaces.
- For a working mine, use site-mandated IT security, data classification, HSE governance, and project-control methods. Never use this prototype to transmit company data to a public cloud without written approval.

## Project layout

```
app.py                 Streamlit web application
analytics.py           Data validation, KPIs, flags and reports
index.html             Standalone, offline and GitHub Pages preview
data/*.csv             Fictional sample project registers
requirements.txt       Python dependencies
.streamlit/config.toml Theme and small upload limit
.github/workflows/ci.yml  GitHub Actions checks
tests/*.py             Analytics, panel and AppTest checks
scripts/test_preview.js  Static-preview logic checks
DEPLOYMENT.md          Account/deployment instructions
TEST_REPORT.md         Local verification and known limitations
```

## v0.3 session workflow update

See [RELEASE_NOTES_v0.3.md](RELEASE_NOTES_v0.3.md). The new **Workflows** tab includes a contractor register, RFIs, an engineering document metadata index and a session backup/restore tool. Actual activity completion can be edited on the Schedule tab. These are **temporary, independent per-visitor edits**; no multiuser database, login or approvals have been implemented. The `index.html` GitHub Pages view is the earlier standalone preview; new workflows are provided in the Streamlit app.
