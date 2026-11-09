## v0.5.3 Light/Dark UI testing

Dual palette definitions, typography contrast, widget/button palette contrast, CSS token usage and Plotly chart color legibility are covered by tests/test_theme.py. GitHub CI also checks the Streamlit config parser, the complete project controls suite, and dashboard render smoke tests. The final live appearance needs browser review in Light and Dark modes.

# PEIMS v0.4 verification status

## Local checks — 9 November 2026

- 31 tests passed, 1 Streamlit-specific test module skipped locally (Streamlit package absent in this environment).
- Node JavaScript preview: 12 panel/project combinations and two report handlers passed.
- Python compile checks passed for the public application, scheduling/cost functions and enterprise source.
- API tests exercise project access isolation, viewer write restrictions, manager-only financial access, audit events, row version conflicts, RFI reference uniqueness, invalid data, and RS256 issuer/audience/expiry validation using a generated test key.
- CPM tests cover two projects, finish-to-start lag calculations, float, cycles and unknown links; CPI forecast tests ensure commitments are not added to actual expenditure.

## Still required

- GitHub Actions full Streamlit AppTest integration check with dependencies installed.
- Post-merge hosted Streamlit browser verification of schedule/cost tabs and existing v0.3 workflows.
- Actual PostgreSQL migration and rollback validation in a disposable **staging** database; no Postgres server is available locally.
- Real OIDC provider token acceptance/revocation and secure infrastructure provisioning; no live enterprise backend is installed.
- Security review, database backups and documented enterprise access controls before company use.

Green tests demonstrate prototype logic, not production-readiness, Newmont endorsement, or site engineering validation.
