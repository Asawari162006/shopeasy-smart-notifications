# Five-minute demonstration

Before class: install the tested environment, run the tests, then `python run.py` in the virtual environment. Check the printed URL and model-loaded banner. All prepared runtime assets work offline.

0:00–0:45 — Simulate. Explain the synthetic-data label and the four layers: observed behavior, estimated disengagement risk, policy decisions, explicit preferences. Click Auto Demo for a separate seven-step practice simulation. Follow Ishita from week 1 through changing engagement, analysis, the planner, and a promotional opt-out. Each step explains what happened, what to notice, and why it matters. Next/Back are user-paced; Play automatically advances every 25 seconds and can be paused. Finish or Exit restores your original simulation. Refresh also returns to your own simulation. To prepare sample personas in your own workspace for the manual presentation below, use Load five-week sample behavior after exiting the tour.

0:45–1:45 — Insights. Compare Aarav, Ishita and Meera using the customer selector. Show rolling observed opens, model output (uncalibrated), and policy tier. Point out the recent behavior override, category pauses, and that KNN has no fabricated feature attribution. Do not claim fatigue or shopping churn.

1:45–2:45 — Simulate. Select Guest. Show insufficient history before enough evidence exists. Choose Open and Click/Save for a notification, ignore or dismiss another, and advance. Explain the view seconds are simulated, not measured. Use scripted weeks to advance faster. Progress continues beyond five weeks.

2:45–3:45 — Preference center and Personalized Plan. Explicitly mute a promotional category, set caps and quiet hours, save, and inspect the suppressed/deferred reasons. Opt out of promotions: order lifecycle updates remain. Disable-all stops both. Explain optional probes only apply to automatic pauses, never explicit mutes or high policy risk. Refresh to show persisted progress.

3:45–4:30 — Baseline comparison. Same candidate IDs and week on both sides; baseline still obeys explicit preferences. Show allowed/deferred/suppressed counts and actual simulated opens/delivered denominators. Suppressed candidates have no imagined response or retention benefit.

4:30–5:00 — Model Evaluation. Show actual split boundaries, purge gaps, candidate validation metrics and final selected test. Explain why high accuracy with only five positive test snapshots is weak evidence; report F1/recall/PR-AUC honestly. Finish with synthetic-data and unseen-customer limitations.

Troubleshooting: if port 8000 is occupied, use `python run.py --port 8001`. If model artifacts are incompatible, `python run.py --prepare` rebuilds them. Missing-model UI displays rule-only fallback and no probability. Reset is scoped to the active simulation. Separately opened tabs have independent session IDs; duplicated tabs may clone browser sessionStorage.

Report demonstration: select the customer and choose Download PDF report. The PDF downloads immediately, with no format chooser or print step. The report separates observed behavior, ML estimates, sending-policy decisions, preferences and limitations.
