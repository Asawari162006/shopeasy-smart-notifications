# UI refinement and customer reports

## What changed

The three main destinations are Simulate, Personalized Plan and Insights. Model Evaluation remains available as a secondary link. The header retains Auto Demo, theme preference and a quieter Reset action. A state-derived workflow identifies recorded weeks, estimate availability and scheduled messages.

Simulate uses a compact customer panel with name search, role hints, selected state and Guest access. The panel collapses on narrow screens. The interactive phone remains the primary response surface, with readable text and native action buttons. Open reveals simulated duration, timing, Click and Save. Every notification must have a chosen response before submission; an explicit Mark remaining as Ignore shortcut is available. Actual reviewed counts and disabled-state explanations are shown. Main-phone nested scrolling was removed.

Sample loading, one-customer scripted playback, Analyze behavior and the guided Auto Demo remain separate and explain their scope. Personalized Plan groups actual scheduled messages, exposes suppressed/unscheduled reasons, compares equal candidate streams, and separates continued/paused categories from advice. Continued interactions use a native modal with Escape support and focus restoration. Insights separates observed behavior, actual uncalibrated model output, rules and advice. Empty-exposure weeks are omitted from engagement bars.

Light/dark palettes use reusable tokens. Text accompanies status colors. Main controls target at least 44px. No external assets, libraries, model training or backend changes were added.

## Downloading a report

Choose a customer, then Download PDF report. The file downloads immediately as `shopeasy-{customer}-week-{week}-report.pdf`, with no format picker, print dialog, HTML or JSON option. A read-only `GET /api/customer/{cid}/report.pdf` endpoint uses the existing simulation header and validates the requested customer. It responds with `application/pdf`, an attachment filename and `Cache-Control: no-store`. Report generation does not advance a week or modify policy state.

ReportLab produces a paginated A4 document with embedded fonts, repeated table headings and page numbers. The report includes weekly behavior, category interest, ML estimate and availability, policy reasons, explicit preferences, upcoming candidate decisions, baseline comparison, recorded actions with duration/timing/click/save, and decision-history summaries. Text is escaped before PDF layout, and synthetic evidence and limitations remain explicit. ReportLab is pinned in requirements.txt and works offline after setup.

## Differences from the older UI guidelines

- The current API provides `model_probability` and prediction availability. The UI preserves that real value and labels it uncalibrated; it does not derive a fake percentage from a tier or call it accuracy.
- The current baseline and adaptive schedules share six candidates (five promotions and one order event). No 12-alert reference bundle exists. The comparison shows the actual equal candidate sets rather than inventing a reference or measured retention improvement.
- `week_engagements` currently represents opened / delivered per completed week, not a weighted composite interaction score. The chart labels that formula explicitly and omits weeks without deliveries. Interest scores use actual exposed-category scores.
- Sample loading fills missing baseline observation weeks through week 5 and preserves existing progress/preferences. It does not replace progress. One scripted week affects only the selected customer, while the guided tour uses an isolated practice simulation.
- Simulation can continue beyond five weeks, and promotional opt-out preserves order updates. The interface describes these states without forcing a false global completion or altering policy rules.

## Files

- `static/index.html`: compact header, workflow, report/reset/continued-interaction dialogs.
- `static/style.css`: consolidated tokens and responsive component styles.
- `static/app.js`: compact selection, reviewed-state submission, timing, plan/comparison, insights, errors and dialogs.
- `static/demo.js`: guided phone tour adapted to the new navigation and report availability.
- `static/report.js`: one-click authenticated-session PDF download.
- `engine/customer_report.py`: paginated PDF generation.
- `app.py`: read-only customer PDF endpoint.
- `requirements.txt`: ReportLab dependency.
- `tests/test_report_ui.js`: direct PDF download contract; Python HTTP tests verify correct customer, media type, filename and unchanged state.
- `README.md`, `docs/DEMO_GUIDE.md`, `docs/VERIFICATION.md`: usage and verification updates.

## Running

From the project directory: `.venv\Scripts\python.exe run.py --port 8004 --no-browser`, then open http://127.0.0.1:8004. If the current server is already running, refresh the browser; the redesign uses static files and needs no backend restart. Python tests require the existing virtual environment; the standalone frontend test uses Node's built-in test runner.

## Limitations

Reports are snapshots of synthetic simulations, not real customer evaluations. Existing probabilities are uncalibrated, and the held-out test has few positive cases. A planned reduction is not causal evidence of improved retention. These backend/model limitations were preserved, not modified as part of this design work. PDF export is direct and does not require browser print support.
