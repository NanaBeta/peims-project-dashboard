# PEIMS v0.5.3 — Native light/dark appearance

- Adds configured **Light** and **Dark** visual modes; select **System / Light / Dark** through Streamlit's top-right Settings → Appearance.
- Reworks sidebar, metrics, hero, cards, project controls, warnings and footer to inherit native theme tokens.
- Removes fixed dark backgrounds from custom shell and Plotly chart labels. Keeps semantic chart colors visible on both light and dark.
- Improves page-menu discoverability by removing the legacy #MainMenu visibility override and adds an appearance hint in Preferences.
- Retains all nine workspaces, compact layout, fictional datasets, calculations and workflows.
- Keeps enterprise backend separate and unhosted; no live company project data or login integration.
