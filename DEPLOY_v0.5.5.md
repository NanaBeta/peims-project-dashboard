# Deployment — v0.5.5 guided workspace UI

The new version is **not automatically published** just because this ZIP was downloaded. Publish it to the `main` branch of `NanaBeta/peims-project-dashboard` for Streamlit Community Cloud to redeploy.

## Changed/new project files

- `app.py` — new default Home and dedicated task flows
- `ui_shell.py` — navigation entries and responsive Home styling
- `experience.py` — pure navigation-page rendering helpers and action prioritization (new)
- `tests/test_streamlit_app.py` — updated Streamlit page journey tests
- `tests/test_ui_shell.py` — updated navigation count
- `tests/test_experience.py` — Home/UI logic and safety tests (new)
- `.github/workflows/ci.yml` — compile the new modules
- `README.md`, release notes — guidance

### Recommended publishing route

1. Extract `PEIMS_v0.5.5_Quick_Upload.zip` locally.
2. Open `https://github.dev/NanaBeta/peims-project-dashboard` (signed in to GitHub). Add/replace the files above **preserving the `tests/` and `.github/workflows/` directories**. Check the Source Control diff before committing.
3. Commit/push as `PEIMS v0.5.5 — guided workspaces` to a review branch first if possible; confirm that GitHub Actions checks pass, then merge to `main`.
4. Refresh the Streamlit app, or use its `Manage app` reboot option if Cloud remains on the wake-up screen.
5. Test Home → Manage schedule → activity details → back → Home; resolve an action, test documents; repeat for both fictional projects and light/dark themes.

Do not deploy real company records. For production, obtain an approved identity provider and secure database staging environment first.
