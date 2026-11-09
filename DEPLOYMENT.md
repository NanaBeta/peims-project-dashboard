# Deploy PEIMS online — v0.2

**Status:** Source is prepared; you must publish it using your own GitHub and/or Streamlit Community Cloud account. No live URL has been created by this package.

## First, upload project files to GitHub

1. Sign in to GitHub: <https://github.com>.
2. Create a repository named, for example, `peims-project-dashboard`.
3. Add the **contents of the unzipped project folder**—not the ZIP file itself—to the repository root. Preserve folders such as `data/`, `.streamlit/`, `tests/`, and `.github/workflows/`.
4. Ensure these files appear at the repository root: `app.py`, `analytics.py`, `requirements.txt`, `index.html`.
5. Do not upload `secrets.toml`, company files or passwords. This package contains no secrets.

**Phone-only note:** GitHub's browser file uploader accepts files and folders in a supported browser, but uploading a multi-folder project from Android can be awkward. The GitHub integration in ChatGPT may simplify publishing after you explicitly connect and authorize it. On GitHub, you can also use the desktop-site option in your mobile browser. Do not post access tokens in chat.

## Option A — Read-only public demo on GitHub Pages

This is the quickest way to get a shareable browser demo.

1. Open your repository, select **Settings → Pages**.
2. Under **Build and deployment**, select **Deploy from a branch**.
3. Select **main**, folder **/(root)**, then **Save**.
4. Use the Pages settings **Visit site** link to get the real URL; test all six tabs and both project selections.

GitHub Free supports Pages for public repositories. GitHub Pages publishes a public site; use synthetic data only. `index.html` is the landing page and needs no server or Python.

Official help: <https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site>

## Option B — Full Streamlit app

1. Open <https://share.streamlit.io> and sign in.
2. Connect GitHub to Streamlit Community Cloud and authorize repository access.
3. Choose **Create app → Yup, I have an app**.
4. Select your GitHub repository, branch `main`, and entrypoint `app.py`.
5. In advanced settings, select Python **3.12**. No secrets or environment variables are required for the sample demo.
6. Deploy, check the logs for errors, and use the resulting verified `*.streamlit.app` URL.
7. Test all seven dashboard tabs, both project choices, a sample CSV import, reset and both report downloads.

The sample dashboard is suitable for a *public demonstration* only. Configure visibility deliberately: public GitHub repos generally lead to public Streamlit apps by default. Streamlit Community Cloud is **not a Newmont-approved data environment**.

Official instructions: <https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>

## Troubleshooting

- **“Module not found”**: check `requirements.txt` is in the repository root and has been committed.
- **“No such file”**: check `data/*.csv` files were uploaded, not just `app.py`.
- **App loads but source data seems missing**: verify the repo path and that CSV files retained their exact names.
- **GitHub Pages shows README instead of dashboard**: ensure `index.html` is in the publishing root and Pages finished deploying.
- **A Streamlit graph or upload fails**: review Streamlit app logs and the GitHub Actions **PEIMS demonstration checks** job; do not assume a green standalone preview test proves the full app works.

## Post-deployment verification checklist

- [ ] GitHub Actions tests pass after dependency installation
- [ ] Public static dashboard loads on Android and desktop browsers
- [ ] Both project selectors work
- [ ] All six browser-preview modules load
- [ ] Browser-preview report downloads work
- [ ] Full Streamlit site loads without errors
- [ ] Seven tabs work for both projects
- [ ] CSV upload and reset work using fictional records
- [ ] All downloadable reports display correct project names and reporting dates
- [ ] No confidential records or credentials are stored on the public site
