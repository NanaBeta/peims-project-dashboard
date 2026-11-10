# PEIMS v0.6 — Spreadsheet Studio & BI-style Analysis Builder

## New functionality

- A new **Spreadsheets & BI** workspace accessible from the Home cards and sidebar.
- An interactive, typed project-register grid for eight editable record collections plus one read-only progress-history collection.
- Existing record IDs, project identity and row count locked; all edits are validated and trigger a recomputation of project controls.
- Excel `.xlsx` workbook export with nine named worksheets, filterable headers, frozen header row and guidance sheet.
- Bounded import of an individual `.xlsx` worksheet with formula rejection, preview, project scope checks, changes summary and explicit apply.
- BI-style grouped analysis on activities, procurement, actions and risks using vetted dimensions/measures, contextual filtering, charts and CSV export.
- Field-name audit events appended to the session history after successful edits.

## Not provided

This is **not a general-purpose Excel formula engine, Power BI semantic model, Primavera P6 implementation or multiuser database**. The live app remains a fictional sample-data demo. Existing backend API migrations remain separate and undeployed.

## Development quality

Python tests, workbook import/export tests, project-scoping rules, CSV formula-injection handling, and Streamlit integration tests are part of the repository CI workflow. Cloud results must pass before release to main.
