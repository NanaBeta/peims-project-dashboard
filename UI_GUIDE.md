# PEIMS interface — v0.5.3

## Light / Dark appearance

Use **⋮ → Settings → Appearance** in the running Streamlit app and select **System, Light, or Dark**. The sidebar's Preferences section explains these steps. This uses native Streamlit theming (including tables, dropdowns, charts and forms) instead of a CSS-only imitation. There is no separate sidebar theme toggle.

The dark preset retains PEIMS navy colors; the light preset uses a pale-gray page, white cards and an ink-blue type palette. Compact layout remains independent.

## Acceptance checklist

1. Check every workspace in both Light and Dark, including hover labels, chart axes, document registers, native data editors, and notification banners.
2. Switch projects and check light/dark presentation at narrow viewport widths.
3. Select System to follow OS preferences.
4. Recheck schedule, cost, and import calculations.
5. Never upload actual Newmont/company-sensitive information to this public demonstration.

Custom chart annotations may require a widget action or refresh after switching appearance on some Streamlit versions.
