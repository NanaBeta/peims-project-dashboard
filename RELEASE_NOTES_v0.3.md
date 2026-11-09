# PEIMS v0.3 — Session Workflows

PEIMS is an independent portfolio prototype for fictional mining projects. It is not affiliated with Newmont.

## New in v0.3

- **Contractor register:** edit, add, and remove demonstration contractors; track work packages, responsible leads, planned finish, progress, and at-risk status.
- **RFI register:** track requests for information, discipline, responsible engineer, due date, criticality and response status; flag outstanding/overdue RFIs.
- **Engineering document index:** track document titles, revisions, review status, owners and reference IDs. **No document files are stored**.
- **Schedule progress editor:** update actual activity completion values and immediately recalculate progress and earned-value controls in that browser session.
- **Workspace history:** session-scoped create/update/delete and progress-edit events. It is **not** a tamper-resistant, multiuser compliance audit log.
- **Backup/restore:** download an entire workspace as a ZIP of CSV data, and import a previously exported v0.3 ZIP with validation.
- **Extended weekly report:** includes deterministic highlights from the workflow registers.
- **Automated checks:** validation, scope isolation, backup integrity, report summary and prior project controls.

## Important limitations

This demonstration app is **public, unauthenticated, and session-only**. A visitor's edits are not shared with other visitors and are not automatically retained. Export a workspace ZIP to preserve fictitious work. GitHub Pages remains a **read-only standalone v0.2 preview**; use the hosted Streamlit app for v0.3 modules.

Do not enter any company-sensitive data, employee details, real contracts, commercial offers, actual mine designs, safety documentation, or confidential project data. A production system would require enterprise-approved access controls, encrypted durable storage, role-based permissions, audit retention, review/approval workflows and organizational authorization before using such information.

## Quick test

1. Open Streamlit and select a project in the sidebar.
2. Open **Workflows > RFIs**, expand **Edit records**, change an existing RFI status, then apply.
3. Open **Workflows > Workspace & history** and download the complete workspace ZIP.
4. Reset the demo workspace and restore the ZIP. Check the RFI status and session history.
5. Switch to the other sample project; records should remain independent.
6. On the **Schedule** tab, expand the activity completion editor and update one percentage; verify command-centre figures recalculate.

## For developers

Run `pip install -r requirements.txt && streamlit run app.py`.
Run `python -m pytest tests/ -q && node scripts/test_preview.js`.
