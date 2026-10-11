# Dataset card: synthetic notification interactions v2

Purpose: educational forecasting of 14-day promotional disengagement; not a real customer dataset. No personal customer information was collected.

Generation: `data/generate_data.py`, random seed 42, 600 customers, 210 observation days starting 2026-01-05 UTC. Nine synthetic generator personas control category response probabilities, temporal changes, response noise, and explicit mute/unsubscribe behavior. Live demonstration personas are a separate scripted presentation layer. Neither generator persona nor live identity is a feature. Customer survival, muting, fixed notification type mix, and the deterministic label introduce strong biases; these are not representative of a retailer.

Files:

- `customers.csv`: synthetic customer ID, generator persona, signup day, preferred time window. Persona is for auditing/charts only.
- `notifications.csv`: canonical timestamp and event ID; category, action, simulated view seconds, click/save flags, mute flag, and simulated order lifecycle reference. Timestamp uses the actual generated send day/hour. Synthetic duration source is explicitly `simulated`.
- `order_events.csv`: simulated shipment lifecycle sources, each linked by an order_event_id from an order update. No quota-filling transactions.
- `subscription_events.csv`: explicit unsubscribe events at their generated midnight check timestamp. These are independent events, recorded before stopping future notifications. They are not fabricated notification exposures.
- `dataset_metadata.json`: schema version, seed, epoch, period and actual counts.
- `reports/snapshots.csv`: trailing-history features, snapshot day and target; blank target is unknown/censored.

The generator's independent order-update draws represent simulated shipment lifecycle events; the app similarly creates one weekly simulated shipment event. No order update is added to fill a promotional quota. This simplification is not a complete order simulator.

Target: at snapshot day s, use notifications strictly before s. Positive if an explicit unsubscribe occurs in [s,s+14), or if at least five future promotional notifications exist and less than 5% are opened. Negative requires at least five future promotional notifications and >=5% opens. Insufficient future exposure or incomplete 14-day follow-up is unknown. An explicit unsubscribe provides a positive even if exposure is low, provided full observation follow-up is available. Previously unsubscribed customers are excluded from future-risk snapshots. Outcomes are behavioral definitions, not fatigue or shopping churn.

Features: trailing 7/21-day overall open rates; latest 7 versus previous 14-day difference; trailing category open rates; prior promotional non-open streak; days since last open (capped at 21); trailing mean simulated viewing duration and click/open rate; prior mute count; dismissed share. A category without exposure has a neutral numerical 0.5 feature; the UI labels its observed interest unknown. Prior non-open streak/mute totals use all prior history. All other recent features use the stated rolling windows. Both offline/live paths share normalization and extraction.

Snapshots every seven days from day 21. Train snapshot days 21–98 (outcomes end 112), validation 119–147 (outcomes end 161), test 168–196 (outcomes end 210). Intermediate snapshots are purged; incomplete late snapshots remain unknown. Partition gap exceeds the 14-day horizon. Future feature windows may naturally contain older training-period interactions; no future outcome is used as a feature.

Limitations: many disengaged customers leave early, leaving only five positive late test snapshots. Synthetic behavior, survivor selection, fixed generator assumptions and correlated repeated snapshots limit interpretation. No causal policy comparison, unseen-customer generalization, probability calibration, fairness claim, or production readiness is established. Real-world deployment requires consented data, a separate unseen-customer holdout, stronger positive support, calibration assessment, operational experimentation, and authentication.

Actual counts, fingerprint, class distributions and dates are generated in `reports/evaluation.json`; charts are regenerated from events rather than estimates of last activity.

