# Architecture and ML pipeline

## Runtime

`run.py` resolves project-relative paths, checks port availability, verifies artifacts, and starts FastAPI. The health check confirms SQLite access and reports model availability. The browser opens only after health success.

The static HTML/CSS/JavaScript interface has Overview, Customer Simulator, Customer Insights, Notification Planner and Model Evaluation views. Assets are local. Each tab sends a random UUID simulation ID. FastAPI's session dependency holds one SQLite `BEGIN IMMEDIATE` transaction across each state mutation, then persists the session plus queryable customer, event, preference, prediction and decision tables. Unique (session_id, event_id) keys and submission IDs prevent duplicate recordings. A submission retry returns its prior success semantics; reusing its ID for different content returns 409. Stale weeks return 409. Invalid actions, IDs, ranges and timezone return 422. A fresh connection retrieves state after restart. SQLite serializes writes; this is appropriate for a small local demonstration, not a high-volume service.

Flow: candidate lifecycle/promotional events → explicit preferences → model/rule policy → quiet-hour/cap scheduler → allowed/deferred/suppressed decisions → delivered simulated interactions → canonical events → rolling features → next analysis. Decision logs store the prediction, preference snapshot, and reasons. Replanning the current week replaces the active plan and records an audit entry; submitting the week records only delivered eligible interactions.

Preferences: category mutes, promotional opt-out, disable-all, daily/weekly caps, quiet hours and IANA timezone, configurable opt-in probes. Category mutes are persistent explicit choices; low-interest pauses are recomputed rules. Probes require an automatically paused category, low/medium policy tier, enabled setting and due interval (default four weeks, minimum two); at most one, within promotional caps. High tier and explicit preferences cannot be overridden by probes. Transactional events require an order lifecycle ID, bypass promotional caps/quiet hours, and obey disable-all.

The five-week sample loader collects scripted baseline observations before personalization, respecting explicit preferences/caps. Subsequent weeks use adaptive delivery. History records the delivery policy; suppressed candidates never receive invented outcomes. Observed promotional trends compare the latest two versus earliest two weeks in a rolling five-week block; no padded or frozen week-five data. Recent category interest uses trailing 21-day opened/delivered rates; at least three exposures plus low rate or three non-opens can pause a category. Explicit evidence, model probability/tier, policy tier/overrides, and preference decisions are separate fields. A recent open rate below 10% can produce a visible conservative high-tier rule override. Tier caps are 5/3/0 promotions per week for low/medium/high, further limited to two slots per currently eligible promotional category and the explicit cap. These are transparent policy conventions, not learned causal optimums.

No-history customers show insufficient history; conservative rules can schedule candidates. Missing or failed model inference returns no probability. Errors recommend rebuilding trusted artifacts. No customer identity is used to force predictions.

## Offline pipeline

1. Generate deterministic 210-day synthetic data and separate subscription events. Plot actual notification open rates and cumulative explicit unsubscribe events.
2. Normalize exact timestamps, action and mute flags, duration values and ordering with the same module as the live simulator.
3. At each snapshot, extract only strictly prior history. Apply the documented 14-day target and minimum five future promotional exposures; unknown/censored targets are excluded from fitting/evaluation. Exclude prior unsubscribes.
4. Use training 21–98, validation 119–147, test 168–196. Each earlier partition's final outcome matures before the next begins.
5. Fit prior baseline, scaled Logistic Regression C∈{0.1,1,10}, Decision Tree depth∈{3,5,7} (minimum leaf 20), and scaled KNN k∈{5,11,21}. Fixed seed 42 for stochastic estimators/generator. No random split of repeated snapshots. A fixed chronological validation block supplies time-aware tuning instead of random cross-validation.
6. Tune each candidate's classification threshold over 0.15–0.85 in steps of 0.05 on validation F1 (recall tie-breaker). Select candidate on validation only. Freeze preprocessing, estimator and threshold. High tier uses the selected threshold; medium uses half as a documented policy convention. No claim that either tier is calibrated.
7. Evaluate selected model once on final test. Generate accuracy, precision, recall, F1, confusion matrix, ROC-AUC and average precision (PR-AUC) when defined. Compare other models on validation only. Do not select again using test results.
8. Save trusted joblib model bundle and JSON metadata: feature schema, dataset SHA-256, training UTC timestamp, dependency versions, partition configuration, model name and thresholds. Export report, snapshot counts/class distributions, and genuine evaluation charts.

Global logistic coefficients or tree impurity importance are labeled by model. Local standardized logistic contributions are supported if Logistic Regression is selected. KNN does not fabricate feature attributions. Behavioral evidence and planner reasons always remain separate from model attribution.

Evaluation concerns future snapshots of existing synthetic customers. A separate customer-group holdout answers unseen-customer generalization. Probabilities have not been evaluated/fitted for calibration. Repeated snapshots are correlated and no independent-sample confidence interval is claimed.

