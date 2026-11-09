# PEIMS v0.2 — verification record

**Verification date:** 9 November 2026 · **Data:** fictional demonstrations only.

## Completed in this environment

- **15 passing Python tests**: baseline analytics, import validation, project relationships, both report calculations, and simulated execution of all seven Streamlit panel functions with Plotly chart serialization.
- **12 passing standalone-preview view combinations**: six JavaScript module functions x two projects, run using a simulated DOM in Node.js.
- **Two simulated Markdown download-handler checks** passed.
- `app.py` and `analytics.py` passed Python syntax compilation.
- Cross-check of embedded `index.html` KPIs against the Python calculation engine passed for both projects.
- Corrected two issues in the original v0.1 standalone preview: an undefined `cost` function reference (the function is named `costs`) and numeric WBS values being compared with `.localeCompare`.

## Not verified yet

- **1 Streamlit AppTest integration test module skipped** because `streamlit` is not installed in this environment and package downloads are unavailable here. It will run in GitHub Actions once dependencies are installed.
- Real browser end-to-end checks were blocked by this environment's browser network-access policy, both for local files and local HTTP; no mobile or visual usability certification is claimed.
- No GitHub repository, GitHub Pages URL, Streamlit deployment, cloud logs, authentication or cloud integration has been created or verified here.

The included GitHub Actions workflow is configured to run Python + Node tests after the project is pushed to a GitHub repository. A passing workflow does not constitute mine safety or production approval.

### v0.3 local development results

- 20 tests passed and 1 Streamlit integration module was skipped locally (Streamlit unavailable in container).
- 12 standalone preview module/project combinations plus two report download handlers passed in Node.js.
- New workflow tests cover field validation, cross-project isolation, add/update history, snapshot roundtrip, unexpected ZIP entries and weekly report summary.
- A GitHub Actions integration test and hosted Streamlit browser check are required before production deployment.
