# Verification record

Verified 2026-10-11 on Windows, Python 3.11.9, using the existing project virtual environment and pinned requirements.

Final command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.test-tmp-final-check
```

**37 passed in 22.17 seconds.** `python -m pip check`: no broken requirements. Python source compilation succeeded.

Coverage includes:

- Generator regression: explicit unsubscribe events persisted before stopping, exact timestamps, order lifecycle provenance.
- Unknown/censored labels for absent/low exposure and incomplete follow-up; known explicit unsubscribe labels.
- Exclusion of prior unsubscribes and 14-day chronological purge invariants; data fingerprint and feature schema.
- Future-event exclusion, deterministic ordering, shared offline/live features, simulated duration and mute-flag normalization.
- Rolling adaptation after week five, no-history and insufficient-history behavior.
- Missing-model and failed-inference behavior: no fabricated probability.
- Explicit mutes, high-risk suppression, opt-out, disable-all and recovery-probe limits.
- Quiet hours crossing midnight, frequency caps, lifecycle-only transactions, duplicate candidate elimination, absolute scheduled-time ordering.
- SQLite connection reopen, persisted progress, scoped reset, isolated sessions, duplicate submissions, stale weeks and invalid inputs.
- Concurrent requests across sessions and concurrent retries of the same submission. FastAPI may resume dependency cleanup on another thread; request-owned SQLite connections support that while preserving transactional serialization. Dependency cleanup completes before the HTTP response, so failed persistence can return an actionable error.
- Real HTTP five-week sample workflow, valid recovering-persona observations before personalization, continued progress beyond week five, static assets and evaluation endpoint.
- Existing persona acceptance cases retained. Three assertions were updated for explicitly defined semantics: high risk pauses promotions rather than sending a contradictory recovery message; promotional unsubscribe retains lifecycle order updates (two cases). No customer identity forces model estimates and no accuracy expectations were imposed.

Browser smoke checks used the actual interface: Overview, automatic demonstration, Insights, Guest Simulator open/click/save and advancing a week, explicit category mute saved through Preferences, Planner reasons and equal candidate-count comparison, Model Evaluation with generated metrics/charts, light/dark themes and a 390-pixel responsive viewport. Refresh/backend restart retained Guest selection and simulated history. The temporary viewport override was cleared. Backend health returned 200; startup verified the artifact fingerprint/schema/dependency version. A deliberate occupied-port startup returned the exact alternative-port instruction.

Environment issue resolved: the restricted execution runner hung in Windows asyncio socketpair initialization before FastAPI startup. Real HTTP tests and the development server were run outside that restriction, using a fresh workspace-local pytest temporary directory. No application workaround or weakened test was used.

Limits: This was a browser smoke check, not an exhaustive screen-reader/accessibility audit, multi-browser matrix, large-scale performance/load test, probability calibration study, or evaluation on real/unseen customers. Only five positive final test snapshots exist. These limitations are visible in the generated evaluation and documentation. Automatic browser launch itself was not used during testing (`--no-browser`); its health-gated logic is implemented. Tests and charts cover only synthetic data and simulated outcomes.

The pre-existing server on default port 8000 was left untouched. The completed project was launched for review at http://127.0.0.1:8004.


## UI refinement and report download verification — 11 October 2026

Frontend redesign leaves the Python API, ML artifacts, dataset, validation thresholds and sending policy unchanged. The existing suite passed again: **37 passed in 28.92 seconds**. JavaScript syntax checks passed for app.js, demo.js and report.js. `node --test tests/test_report_ui.js` passed: the actual exporter retains the original selected-customer snapshot even after later mutation, preserves recorded timing/click data, and escapes script-like text in HTML.

Actual browser checks in an isolated simulation covered name search/no results, role-hint toggling, Guest selection, disabled submission before review, selecting Open/read duration/response timing/Click, marking remaining messages Ignore, actual reviewed counts, saving a manual week, same-customer navigation, sample loading, Analyze behavior, personalized schedule and same-candidate comparison, continued interaction dialog submission, Escape/Close and focus restoration, insights with actual values and empty-history states, Model Evaluation, theme switching, confirmed reset and cancellation, and Auto Demo automatic advancement/pause/exit restoring the original workspace. A deliberately invalid timezone produced a readable validation error and Retry control without losing context; correcting it saved successfully. No unexpected console warnings/errors were captured.

HTML and JSON reports for Ishita were downloaded through the actual browser buttons. The filenames, customer ID, current week, completed history and required report sections were checked against the downloaded files. Standalone file-URL visual preview is blocked by the browser tool’s URL policy, so that preview was not performed. Browser Print / Save as PDF was implemented but PDF printing was not exercised; PDF output depends on the user’s browser.

Simulate, Personalized Plan and Insights were checked at **1440, 1024, 768 and 390 CSS pixels**, with no page-level horizontal overflow. The phone remained visible, with widths of approximately 343–400px. Screenshots were visually inspected in light and dark themes, including 390px mobile. The temporary viewport override was reset. Text-contrast calculations for the implemented primary-button, secondary-text and status pairs all exceeded 4.5:1; the dark selected accent pair was 4.62:1. This is not a full screen-reader or multi-browser accessibility audit. A full backend outage was not induced during this frontend verification.

The original simulation was preserved; all mutating checks ran in a separate test tab. The current local server remains at http://127.0.0.1:8004. See UI_REFINEMENT.md for implementation files and older-guideline/API differences.

## Direct PDF downloads — latest update

Replaced the HTML/JSON format dialog with a single Download PDF report button. The new read-only customer endpoint returns application/pdf as an attachment and preserves the current simulation. ReportLab is pinned in requirements.txt; generation works offline after setup. Existing Python regression tests plus the PDF endpoint test passed: **38 passed in 35.44 seconds**. The frontend direct-download contract test passed. Dependency checks passed.

Verified the actual button downloads a .pdf directly, with no format chooser or print step, including after the final pagination update. Parsed required sections and rendered all seven pages of the five-week Ishita report with Poppler. Inspected the rendered pages for wrapping, tables, headings, grouped interaction records and page footers. The live server was restarted on port 8004 with the final generator. This supersedes the earlier HTML/JSON report and print-to-PDF workflow described in historical verification notes above.
