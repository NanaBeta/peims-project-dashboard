# PEIMS v0.5.2 — UI design guide

## Structure

The sidebar holds **project context** and **workspace navigation**. The main area has a project identity panel, a persistent data-safety note, a section header, and selected analyses/workflows.

| Screen | Primary question |
|---|---|
| Command centre | Which exceptions and performance indicators need attention? |
| Planning & schedule | Which activities are slipping, and what does the limited CPM model indicate? |
| Cost & commercial | How are EV, AC, CPI and illustrative completion costs trending? |
| Procurement | Which orders are late, expensive, or critical? |
| Risks & actions | Which open risks and actions require attention? |
| Analytics studio | How do schedule and cost exposures vary by responsible owner? |
| Reports | What source-based draft can be exported for review? |
| Workflows | Which contractors, RFIs and document metadata need updating? |
| Data studio | What session-local demo datasets are in use? |

## Visual rules

- Dark navy foundation, restrained warm-amber interactive accent, teal for progress, and red/amber for flagged conditions.
- Clear distinction between *snapshot date* and real time; no implied live telemetry.
- Status badges identify exception **categories**, not an overall performance certification.
- User-controlled compact layout, no new destructive controls, and HTML-escaped project details.
- Desktop responsive defaults plus single-column/compact treatments on narrow screens; the Streamlit mobile sidebar can be collapsed.

## Data & safety limits

All records are fictional. Public Streamlit runs session-only; ZIP export/restore is necessary to save manual changes. Backend PostgreSQL/OIDC modules exist as separate source but are not connected to this UI. No actual Newmont project documents, identities, costs, mine layouts, or security data belong in this demonstration.
