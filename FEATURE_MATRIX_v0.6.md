# PEIMS v0.6 | Engineering software capability map

**Status:** Public portfolio prototype. All project data are fictional. No Newmont deployment or system access.

## Research-informed feature mapping

| Established product | Actual feature model | PEIMS v0.6 | What's needed for deeper parity |
|---|---|---|---|
| Excel | Multiple named worksheets, editable typed cells, validation, sort/filter, calculated columns, workbook exchange | **Partial:** Project-scoped typed data grid, multi-sheet XLSX export, safe per-sheet XLSX import, validation against project-controls engine, CSV, computed read-only activity columns | Full formula engine, cell references and recalculation, multi-row insert/delete, undo history, rich sheet formatting, coauthoring |
| Power Query | Sources, repeated transformations, type changes, joins and refresh | **Planned:** Import uses existing data validators; no custom transformation pipelines | Controlled ETL connectors, transformation history, schema lineage, scheduled refresh |
| Power BI | Reusable measures and semantic models, cross-filtering, drill-through, interactive visuals, dashboards | **Partial:** Fixed measure catalog, grouped totals, dataset filters, linked source-record preview, chart and table, CSV export | Semantic model, saved report definitions, interactive cross-visual linking, dimension relationships, licensed Power BI embedding |
| Primavera P6 | WBS, activity codes, calendar/shift schedules, multiple baselines, predecessor relationships, float, resource assignments and leveling | **Partial:** Existing WBS register, simplified finish-to-start CPM with float, illustrative baseline comparisons | Working-day calendars, leads/lags, dependency types, resource and cost assignments, baseline approval and snapshots, schedule-risk simulation, XER/XML interchange |
| SAP / Contruent | Procurement, commitments, coding, cost control, contracts and change management | **Partial:** Cost and procurement registers, earned value, CPI-based scenario forecasting | Purchase requisitions, approval authorities, change orders, commitments/actual reconciliation, ERP integration and authoritative audit trail |
| Aconex | Controlled project documents, RFIs, workflows, transmittals and approvals | **Partial:** Register metadata, RFI statuses and session edit events | Real documents, permissions, revision archive, controlled transmittals, signatures and immutable audit history |

## Why the new Spreadsheet Studio is part of PEIMS (not a separate app)

Every editable worksheet is a *view over the existing project records*, not its own unrelated spreadsheet. Editing `activities` changes the inputs to physical progress, earned value and schedule analysis. Editing `costs` changes financial KPIs. Editing `procurement` changes late-delivery alerts. This synchronization applies **within the current browser session only**.

## Design invariants

1. Existing project IDs, record IDs and row counts are immutable inside Spreadsheet Studio.
2. Every edit is validated and recomputed against all projects before being committed to the session.
3. Workbook imports accept only `.xlsx`, are bounded in size/rows and reject formula cells; no VBA, macros or arbitrary code execution.
4. Excel exports use non-executing string writes and CSV exports escape spreadsheet formula injection.
5. Calculated columns and BI-style measures are server-defined—not user-supplied code or formulas.
6. Sensitive or company records must not be uploaded into the public demo.
7. Real collaboration still requires the separately written, unhosted FastAPI/PostgreSQL backend plus authenticated roles and security review.

## Next implementation sequence

**v0.7 – P6-style project scheduler:** resource calendars, activity relationship types, baseline versions, resource assignments, progress-entry workflows, schedule-quality diagnostics.

**v0.8 – Commercial controls:** cost breakdown structure, cost codes, commitments, change orders, contract payment certificates, earned-value baselines, estimate-to-complete input forms.

**v0.9 – Analytics models:** saved filters and views, interactive drill-through, cross-filtered charts, data lineage, exportable report templates and transformation pipelines.

**Enterprise integration (separately gated):** authenticated PostgreSQL staging, internal source connections, authorized P6/Power BI/SAP/Aconex adapters, concurrency controls, backup/restore and formal role-based access tests.

## Reference documentation

- Excel for the web features: https://learn.microsoft.com/en-us/office365/servicedescriptions/office-online-service-description/excel-online
- Power Query: https://support.microsoft.com/en-us/excel/about-power-query-in-excel
- Power BI cross-filtering: https://learn.microsoft.com/en-us/power-bi/explore-reports/end-user-interactions
- Power BI drillthrough: https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-drillthrough
- Oracle Primavera P6 Professional user guide: https://docs.oracle.com/cd/G48902_01/English/User_Guides/p6_pro_user/toc.htm
- P6 baseline concepts: https://primavera.oraclecloud.com/help/en/user/89344_1.htm
- Power BI embedded analytics licensing and security: https://learn.microsoft.com/en-us/power-bi/guidance/powerbi-implementation-planning-usage-scenario-embed-for-your-organization


### v0.6.1 — row creation support

The Worksheet Grid now supports validated creation of activities, procurement orders, risks, actions, contractors, RFIs and document metadata, as well as newly added records imported from Excel. Adding an activity automatically creates its required cost-ledger entry with zero expenditures. This is a structured project register, not a general-purpose formula engine; deletion of existing records and independent financial transactions are not supported in this grid.
