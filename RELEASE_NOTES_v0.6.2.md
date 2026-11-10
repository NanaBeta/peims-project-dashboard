# PEIMS v0.6.2 — Smart, reusable data-entry suggestions

## Added

- **Quick Add with suggestions** inside Spreadsheet Studio → Worksheet grid on Activities, Procurement, Risks, Actions, Contractors, RFIs, and Documents. A searchable picker proposes values already used by the *selected project*. You can type a completely new value where the field is open-ended.
- **Suggested dropdowns in the editable grid** for owner, discipline, supplier, category, source, company, leads, priority, status, etc. Turn off *Suggest previously used values in grid* for unrestricted text editing. Status and other controlled values remain subject to the existing backend validators.
- **Automatic record ID proposals** for Quick Add. IDs remain editable, checked globally for collisions, and validated on save.
- **Practical defaults** for statuses, priorities, dates and new record progress. Risk probability/impact require explicit 1–5 selection. New activities still create linked zero-cost records.
- **Project-scoped suggestions**: no values from other projects are displayed. New labels become available after a successful save, without storing a separate centralized directory.

## Important limitations

The public Streamlit app is still a **fictional session-only demonstration**, not an authenticated multiuser system. The suggestion catalog is derived from the current session's existing project records and is not shared between browsers or persisted without a workspace backup. Quick Add does not use AI inference, train on company data, or connect to Newmont systems. Excel upload rules are unchanged.

## How to use

1. Choose **Home → Open spreadsheets → Worksheet grid**.
2. Select a sheet such as **Actions** or **Activities & WBS**.
3. For rapid editing, keep **Suggest previously used values in grid** on and choose from cell dropdowns. Turn it off to type a new value directly in a grid cell.
4. For new records, expand **＋ Add an entry with suggestions**, choose a previous owner/discipline/etc. or type a new one, then save.
5. Download a workspace backup from **Workflows → Workspace & history** to retain session edits.
