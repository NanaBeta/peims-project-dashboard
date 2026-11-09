# PEIMS v0.4 deployment — two distinct services

The public sample-data **Streamlit dashboard** is already deployed from the repository. When the `main` branch is updated and CI passes, Streamlit Community Cloud normally redeploys the dashboard automatically. The separate **enterprise FastAPI/PostgreSQL/OIDC backend is NOT hosted**.

## Dashboard (fictional data only)

- GitHub repo: <https://github.com/NanaBeta/peims-project-dashboard>
- Static browser preview: <https://nanabeta.github.io/peims-project-dashboard/>
- Streamlit: use the app URL in your Streamlit Community Cloud account, not a guessed hostname.
- App entrypoint: `app.py`; branch: `main`; Python: `3.12`.
- No environment secrets or database credentials are required for the sample-data Streamlit app.
- After updates, test Command centre, Schedule (including limited CPM), Cost control (including CPI estimate), Procurement, Risks & actions, Reports, Data studio and Workflows for both fictional projects. Test CSV downloads/ZIP backups only with demonstration records.

GitHub Pages `index.html` remains the older standalone preview, **not** the live Python analytics runtime.

## Separate enterprise backend — NOT for public demo deployment

Do **not** enter an organization database URL into Streamlit Community Cloud. See [ENTERPRISE_SETUP.md](ENTERPRISE_SETUP.md) and [SECURITY.md](SECURITY.md) for the isolated API foundation, required PostgreSQL/OIDC environment and threat limitations.

Enterprise deployment requires a designated and approved HTTPS API service, managed PostgreSQL, issuer/JWKS/audience configuration, secret storage, membership provisioning and operational security validation. Nothing automatically provisions those services from GitHub or Streamlit.

## Verification checklist

- [ ] GitHub Actions main-branch test workflow is green for release commit
- [ ] Streamlit dashboard shows `PEIMS / CONTROLS 0.4`
- [ ] Two fictional projects switch correctly
- [ ] Schedule shows network modeled finish, total float and critical activities
- [ ] Cost controls show EAC, ETC and VAC with assumptions
- [ ] Workflows, imports, report exports and workspace backup still function
- [ ] No company-sensitive content, authentication secret or private DSN has been uploaded

Use simulated data exclusively until enterprise authorization and security reviews are complete.
