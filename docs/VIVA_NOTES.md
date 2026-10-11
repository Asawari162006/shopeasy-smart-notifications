# Viva notes

- **Problem:** Estimate future promotional disengagement from prior notification behavior. Shopping churn and psychological fatigue are not measured.
- **Synthetic data:** Seeded generator, nine data personas, 600 customers and 210 days. Live sample personas are scripted for demonstration; their names/roles are never model features.
- **Target:** Explicit promotional unsubscribe in the following 14 days, or <5% opens with at least five promotional exposures and full follow-up. Unknown if exposure/follow-up is inadequate. Exclude customers already unsubscribed.
- **Features:** Rolling 7/21-day rates, previous-versus-recent trend, category open rates, prior non-open streak, days since open, simulated duration, click/open rate, mutes, dismissals. Only events strictly before the snapshot are used. Offline and live share extraction.
- **Logistic Regression:** Linear log-odds model; scaled inputs; interpretable signed coefficients. Limited by linear relationships. It is not automatically calibrated in this dataset.
- **Decision Tree:** Nonlinear threshold rules, readable paths/importances; depth and leaf-size limits reduce overfitting. Importance is not causal and may be biased toward some features.
- **KNN:** Neighbor voting in scaled feature space; tune k on later validation data. Sensitive to scaling and distribution shift, can give extreme probabilities, and lacks a built-in faithful feature attribution.
- **Dummy prior:** Predicts using training prevalence without behavioral features; gives context for class imbalance.
- **Splits:** Chronological train/validation/test, with a purge gap longer than the 14-day outcome horizon. Earlier labels fully mature before the next period begins. Random repeated-snapshot CV would leak temporal structure. Fixed future validation block tunes models/thresholds.
- **Selection:** Validation F1, recall tie-breaker. Test is used only after selection. Training-fitted scaler is never refitted on test. No promised target accuracy.
- **Metrics:** Accuracy=(TP+TN)/N; precision=TP/(TP+FP); recall=TP/(TP+FN); F1 is their harmonic mean. ROC-AUC ranks positives against negatives. PR-AUC here means average precision; especially useful with rare positives. Confusion matrix shows actual error counts.
- **Current result:** Selected KNN k=11; final test TN=1444, FP=6, FN=4, TP=1. Precision=0.1429, recall=0.20, F1=0.1667. High accuracy reflects class imbalance. Only five positive late test snapshots make strong conclusions inappropriate.
- **ML versus rules:** Model predicts uncalibrated behavioral risk. Rules set tiers, category pauses, quiet hours, and caps. Preferences override promotional policy. An observed low-open rule override is visibly separate from the model output.
- **Recovery probes:** Configurable opt-in, limited interval and count; automatic pauses only, never explicit mutes/opt-out/high policy tier. Within caps. They are not proven to improve retention.
- **Transactions:** Generated from simulated order lifecycle events, independent of promotional quota. Promotional opt-out preserves transactions; disable-all stops both.
- **Persistence:** SQLite transactional session state plus event/preferences/prediction/decision records. Per-tab UUID, submission idempotency, typed validation. Local educational system has no production authentication.
- **Fair comparison:** Same candidates/time for baseline and adaptive. Only delivered simulated notifications have observed responses. No imputed outcomes for suppression and no causal retention estimate.
- **Limitations/future work:** Synthetic assumptions, survivor bias, scarce late positives, correlated snapshots, no calibration study, no unseen-customer holdout, no causal experiment. Evaluate consented real data and calibration before any production claim.

