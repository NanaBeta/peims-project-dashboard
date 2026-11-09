# PEIMS user interface guide — v0.5.3

## Choose the visual theme

In the live Streamlit app, open the **top-right app menu (⋮)**, choose **Settings**, and select **System**, **Light** or **Dark** under **Appearance**. The application defines both branded modes in `.streamlit/config.toml` using Streamlit's native `[theme.light]` and `[theme.dark]` configuration.

- **Dark:** navy canvas, darker sidebar, high-contrast text and softly bordered panels. The original PEIMS appearance.
- **Light:** pale off-white canvas, white cards, cool-grey sidebar and ink-blue text for daytime work and presentations.
- **System:** uses the viewer's Streamlit/OS appearance preference.

The **Preferences** area in the PEIMS sidebar explains how to open the native theme setting. It also includes the independent **Compact layout** toggle for smaller screens. The theme setting is controlled by Streamlit; this avoids creating a misleading appearance selector that leaves native data grids dark.

## Layout and navigation

The left-side **Active project** selector sets the reporting context. **Workspace navigation** offers nine workspaces. The compact project banner surfaces key metadata and exception categories; detailed panels render only for the selected workspace.

## Acceptance checks

1. In **Light** mode, visit Command centre, Schedule, Cost control, Procurement, Risks & actions, Analytics studio, Reports, Workflows and Data studio. Confirm text, inputs, tables, heatmap, chart axes and hover panels are readable.
2. In **Dark** mode, repeat the page navigation and check both projects.
3. Switch to **System** and confirm the app reflects the viewer's OS setting.
4. Use Compact layout and verify components remain legible at typical laptop and mobile widths.
5. Verify all core calculations and imports behave as before.

This is a demonstration app, not an approved engineering decision or company data environment.

## v0.5.4 mobile-first enhancements

On the Command centre, use Quick Access for a one-tap jump to Schedule, Cost & forecast, Procurement, or Reports. The shortcut changes the same workspace selection used by the sidebar.

The project card displays actual progress, linear-baseline progress and the gap separately. The colored fill is actual completion and the vertical marker denotes the linear baseline assumption; the legend spells out both.

For appearance use **⋮ → Settings → Appearance** and choose Light, Dark, or System. The compact-layout toggle is in the sidebar; Appearance and Workspace Information have collapsible details to save space on phones.
