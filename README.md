# ShopEasy Smart Notifications

An undergraduate AIML mini-project that predicts **future promotional disengagement** from synthetic notification interactions, then applies an explainable policy and explicit customer preferences. Low engagement does not establish psychological fatigue or shopping churn.

## Windows PowerShell setup

Open this folder in VS Code. Python 3.11.9 was tested.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Activation is optional. These commands avoid PowerShell execution-policy changes. Installation needs package access once; the prepared demonstration uses no internet, paid services, remote fonts, CDN scripts, or external APIs.

Open the exact URL printed in the terminal. Default: http://127.0.0.1:8000. If another server uses that port:

```powershell
.\.venv\Scripts\python.exe run.py --port 8001
```

Options:

```powershell
# Explicitly regenerate synthetic data, model, charts and evaluation, then exit
.\.venv\Scripts\python.exe run.py --prepare
# Start without automatically opening a browser
.\.venv\Scripts\python.exe run.py --port 8001 --no-browser
# Run correctness, persona and real HTTP integration tests
.\.venv\Scripts\python.exe -m pytest -q
```

`SHOPEASY_PORT` also configures the default port. Paths resolve from the project directory. Startup checks dataset version/period, feature schema, dataset SHA-256 fingerprint and scikit-learn version. Missing/incompatible artifacts are regenerated with a clear message. Only load this project's trusted joblib file. The browser opens after `/api/health` succeeds. Stop with Ctrl+C. Port conflicts are reported before preparing artifacts.

## Demonstration

Choose **Auto Demo** for a seven-step narrated walkthrough of Ishita’s notifications, changing behavior, risk estimate, plan, and promotional opt-out. Use **Next** and **Back** at your own pace, or **Play automatically** for 25 seconds per step (pauses when the tab is hidden). **Exit demo** or **Finish** restores your saved workspace. The tour uses a separate practice simulation; refreshing exits the tour and returns to your own session. Then explore Insights, Personalized Plan, and Model Evaluation. For manual interactions, choose Guest in Simulate. The simulated phone is the working interface at every window size: tap Open, Ignore, Dismiss, Mute category, or Opt out directly on each phone notification. Open reveals simulated reading time, Click and Save. Review every notification (or explicitly Mark remaining as Ignore), then tap Submit week inside the phone to apply the responses and receive the next week’s plan. The guided tour also shows real recorded responses and the personalized inbox on a phone. Open, ignore, dismiss, mute, click or save; advance as many weeks as desired. Preferences are within the selected customer's profile. Each new week replans and recalculates analysis. The five-week sample phase collects scripted baseline observations before personalization (respecting explicit preferences and caps), so recovering personas have genuine simulated observations. Subsequent manual/scripted weeks use the adaptive delivered schedule. Each history week records its delivery policy.

Three completed weeks and at least six delivered events in the last 21 days are needed for a model estimate. Before that, the UI explicitly shows insufficient history and uses a conservative rule schedule. Missing/inference-failed models produce `null` probability and a visible rule-only fallback, never a fake score.

A promotional unsubscribe preserves transactional order lifecycle updates. **Disable all** stops both. Explicit mutes prohibit recovery probes. High policy risk suppresses all promotions and probes. Quiet hours affect only promotions; equal start/end disables them. Daily/weekly caps include scheduled promotions moved within the week. Deferred candidates without a scheduled time are not delivered or counted as observed engagement; next week brings a new candidate stream for reconsideration.

## Customer reports and refined workflow

Use the three main destinations: **Simulate**, **Personalized Plan**, and **Insights**. The compact customer panel supports name search, role hints, and Guest free play; it collapses on narrow screens. The workflow indicator uses recorded weeks, actual prediction availability and the upcoming schedule. The plan includes a same-candidate baseline comparison and a keyboard-operable **Continue as this customer** dialog. Reset asks for confirmation.

Select a customer, then click **Download PDF report**. A PDF downloads immediately, with no format picker or browser print step. It contains observed behavior, the ML estimate, policy decisions, explicit preferences, all upcoming candidates, recorded interactions and decision history. Synthetic results and limitations are clearly labeled. Reports are generated offline by ReportLab through a session-scoped endpoint and do not change simulation progress. No HTML or JSON report options are offered.

The redesign preserves existing API contracts, datasets, model artifacts, thresholds and scheduling rules. A new read-only customer PDF endpoint provides direct downloads. See [UI refinement notes](docs/UI_REFINEMENT.md) for the older-guideline differences, file list, and verification.

Run `node --test tests/test_report_ui.js` for the report snapshot/escaping test; the Python regression suite remains `python -m pytest -q`.

## Persistence and isolation

SQLite lives at `data/shopeasy.sqlite3` (`SHOPEASY_DB` can override it). Customers, preferences, interaction/subscription events, predictions and decision logs persist. Each tab uses its own random simulation ID in sessionStorage and an API header; refresh and backend restart retain it. Separately opened tabs have separate simulations; browsers that clone sessionStorage when duplicating tabs may intentionally clone that ID. The cookie is a fallback for API clients. This is a local educational demo with no authentication; simulation IDs are not production access controls. Closing a tab may discard its browser sessionStorage ID. Reset clears only the active simulation's records. Theme preference is local to the browser.

## Results and limitations

See the live Model Evaluation page and generated [report](reports/model_report.md), [JSON](reports/evaluation.json), and charts. The selected model is evaluated once on the final chronological test. All candidate comparison metrics are **validation** metrics. Logistic Regression and KNN use training-fitted scaling; Decision Tree and a prior baseline are also compared.

The regenerated dataset has 600 customers over 210 days. Positive examples become rare late in the observation period because many disengaged customers unsubscribe earlier. Only five positive test snapshots remain: accuracy is misleading on its own. The current selected KNN model has test recall 0.20, precision 0.1429, F1 0.1667, ROC-AUC 0.8354, average precision 0.0918. These are descriptive synthetic results, not a promise of production performance. Probabilities are **uncalibrated**. Repeated snapshots are correlated. This evaluates future behavior of existing synthetic customers, not entirely unseen customers.

## Project guides

- [Dataset card](docs/DATASET_CARD.md)
- [Architecture and ML pipeline](docs/ARCHITECTURE.md)
- [Five-minute demonstration](docs/DEMO_GUIDE.md)
- [Viva notes](docs/VIVA_NOTES.md)
- [Verification](docs/VERIFICATION.md)

The original ten sample personas, Guest mode, message library, deterministic six-candidate weekly schedule, phone preview concept, and light/dark themes are preserved. Transactional candidates have a simulated order shipment lifecycle ID. Baseline and adaptive comparisons share exactly the same candidate IDs and week; the baseline respects explicit preferences and caps. No causal retention improvements or responses to suppressed notifications are inferred.


