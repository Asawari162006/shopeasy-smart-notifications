"""
ShopEasy Smart Notifications - Feature Engineering Module
Computes rate-based rolling features both for offline training snapshots
and for live 5-round interactive sessions.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone

EPOCH = datetime(2026, 1, 5, tzinfo=timezone.utc)


def normalize_event(event):
    """Canonical schema used for both persisted live and synthetic events."""
    e = dict(event)
    e["notification_type"] = e.get("notification_type", e.get("type"))
    if e.get("timestamp"):
        e["day"] = (datetime.fromisoformat(e["timestamp"]) - EPOCH).total_seconds() / 86400
    else:
        e["day"] = float(e["day"]) + float(e.get("hour", 0)) / 24
    e["action"] = e.get("action") or "ignored"
    e["view_seconds"] = float(e.get("view_seconds", {"quick_glance": 2, "few_seconds": 7, "read_fully": 25}.get(e.get("duration"), 0))) if e["action"] == "opened" else 0
    e["muted_type"] = int(bool(e.get("muted_type", 0)) or e["action"] == "muted")
    if e['muted_type'] and e['action'] != 'opened':
        e['action'] = 'muted'
    e["clicked"] = int(bool(e.get("clicked", False)))
    e["saved"] = int(bool(e.get("saved", False)))
    return e


def history_events(history):
    return sorted([normalize_event(n) for h in history for n in h.get("notifications", [])], key=lambda e: (e["day"], e.get("event_id", e.get("id", ""))))


def extract_live_features(history):
    events = history_events(history)
    day = max((h["week"] for h in history), default=0) * 7
    return extract_snapshot_features_from_events(events, day)

FEATURE_COLUMNS = [
    "open_rate_7d",
    "open_rate_21d",
    "trend_7d_vs_14d",
    "open_rate_offer",
    "open_rate_new_arrival",
    "open_rate_price_drop",
    "open_rate_order_update",
    "consecutive_ignore_streak",
    "days_since_last_open",
    "avg_view_seconds",
    "click_rate",
    "mute_count",
    "dismissed_share"
]


def extract_snapshot_features_from_events(events, snapshot_day):
    """
    Fast feature extraction from pre-sorted list of events:
    each event is a dict or named tuple with:
    day, hour, notification_type, action, response_delay_minutes, view_seconds, clicked, saved, muted_type, unsubscribed
    """
    # events up to snapshot_day
    prior = sorted([e for e in events if e["day"] < snapshot_day], key=lambda e: (e["day"], e.get("event_id", e.get("id", ""))))
    w21 = [e for e in prior if e["day"] >= snapshot_day - 21]
    w7 = [e for e in prior if e["day"] >= snapshot_day - 7]
    w14 = [e for e in prior if snapshot_day - 21 <= e["day"] < snapshot_day - 7]

    n_w7 = len(w7)
    open_7d = sum(1 for e in w7 if e["action"] == "opened")
    open_rate_7d = (open_7d / n_w7) if n_w7 > 0 else 0.0

    n_w21 = len(w21)
    open_21d = sum(1 for e in w21 if e["action"] == "opened")
    open_rate_21d = (open_21d / n_w21) if n_w21 > 0 else 0.0

    n_w14 = len(w14)
    open_14d = sum(1 for e in w14 if e["action"] == "opened")
    open_rate_14d = (open_14d / n_w14) if n_w14 > 0 else open_rate_21d

    trend_7d_vs_14d = open_rate_7d - open_rate_14d

    def get_type_rate(type_name):
        type_events = [e for e in w21 if e["notification_type"] == type_name]
        if not type_events:
            return 0.5
        return sum(1 for e in type_events if e["action"] == "opened") / len(type_events)

    open_rate_offer = get_type_rate("offer")
    open_rate_new_arrival = get_type_rate("new_arrival")
    open_rate_price_drop = get_type_rate("price_drop")
    open_rate_order_update = get_type_rate("order_update")

    # Consecutive promo ignore streak
    promo_prior = [e for e in prior if e["notification_type"] != "order_update"]
    streak = 0
    for e in reversed(promo_prior):
        if e["action"] != "opened":
            streak += 1
        else:
            break

    # Days since last open
    opened_prior = [e for e in prior if e["action"] == "opened"]
    if opened_prior:
        last_day = max(e["day"] for e in opened_prior)
        days_since_last_open = min(21.0, float(snapshot_day - last_day))
    else:
        days_since_last_open = 21.0

    # View seconds and clicks in 21d
    opened_21 = [e for e in w21 if e["action"] == "opened"]
    if opened_21:
        avg_view_seconds = sum(e["view_seconds"] for e in opened_21) / len(opened_21)
        click_rate = sum(e["clicked"] for e in opened_21) / len(opened_21)
    else:
        avg_view_seconds = 0.0
        click_rate = 0.0

    mute_count = float(sum(e["muted_type"] for e in prior))
    dismissed_share = (sum(1 for e in w21 if e["action"] == "dismissed") / n_w21) if n_w21 > 0 else 0.0

    return {
        "open_rate_7d": float(open_rate_7d),
        "open_rate_21d": float(open_rate_21d),
        "trend_7d_vs_14d": float(trend_7d_vs_14d),
        "open_rate_offer": float(open_rate_offer),
        "open_rate_new_arrival": float(open_rate_new_arrival),
        "open_rate_price_drop": float(open_rate_price_drop),
        "open_rate_order_update": float(open_rate_order_update),
        "consecutive_ignore_streak": float(streak),
        "days_since_last_open": float(days_since_last_open),
        "avg_view_seconds": float(avg_view_seconds),
        "click_rate": float(click_rate),
        "mute_count": float(mute_count),
        "dismissed_share": float(dismissed_share)
    }


def extract_snapshot_features(cust_notifs, snapshot_day):
    events = [normalize_event(e) for e in cust_notifs.to_dict("records")]
    return extract_snapshot_features_from_events(events, snapshot_day)



