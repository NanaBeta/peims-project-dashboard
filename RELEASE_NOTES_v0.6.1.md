# PEIMS v0.6.1 — Add new spreadsheet records

This targeted usability fix allows **creating new rows** in project-scoped Spreadsheet Studio worksheets, including from exported Excel workbooks.

- **Editable grid:** Use the add-row control at the bottom of activities, procurement, risks, actions, contractors, RFIs, or documents. Supply a unique record ID and all required fields. Save with **Validate & apply worksheet changes**.
- **Project association:** New records are attached to the currently selected project; cross-project insertions are rejected. Existing IDs cannot be renamed or deleted.
- **Activity/cost integrity:** Adding an activity creates its matching cost ledger entry with zero actual cost and zero committed cost. You may edit this ledger entry afterward, but cannot add arbitrary unmatched cost entries.
- **Excel exchange:** Added rows can also be imported from exported .xlsx worksheets. Formula and macro restrictions remain enforced.
- **Safety:** Validation is atomic across all projects, session history records new entries, and all changes remain browser-session-only until manually backed up. Do not upload real company information.

Not supported: deleting existing rows in Spreadsheet Studio, free-form Excel formulas, persistent multiuser workbook storage, or independent cost transactions outside the activity-ledger model.
