# PEIMS v0.5.5.2 — Streamlit header and responsive-layout fix

## Problem observed
The Share / edit / options toolbar was visually overlapping the first PEIMS content row in narrowed windows. The Home welcome card and Command-centre return button were partly clipped. The previously forced `.block-container` top padding was replacing Streamlit's normal header-aware spacing.

## Changes
- Add native `[theme] paddingTop = "1.4rem"`, allowing Streamlit to account for its header height.
- Remove all `.block-container` top-padding overrides, including compact and narrow-screen rules, while preserving side and bottom padding.
- Set `initial_sidebar_state="auto"` so mobile and narrow screens can prioritize main content.
- Present Home navigation choices in two columns instead of three.
- Keep both themes, project controls, and session-only data safeguards.

## Verification
68 local Python tests passed; one Streamlit test module skipped locally.
A browser-layout simulation with fixed 60px toolbar and native-equivalent top inset at 390, 768, 1024, and 1440 px showed no overlap or horizontal overflow.
Cloud integration checks must pass before merging. Hosted-browser confirmation remains necessary.

## After publishing
If Streamlit retains the previous styling, reboot PEIMS from Community Cloud, refresh, then test Home and Command centre with a narrow browser window.
