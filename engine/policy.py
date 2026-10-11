"""Transparent policy decisions are separate from model estimates and preferences."""
from pathlib import Path
import joblib
import pandas as pd
from ml.features import FEATURE_COLUMNS, extract_live_features, history_events
ALL_TYPES = ['offer', 'new_arrival', 'price_drop', 'order_update']
PROMO_TYPES = ALL_TYPES[:3]
TYPE_DISPLAY_NAMES = dict(zip(ALL_TYPES, ['Offers & Sales', 'New Arrivals', 'Price Drops', 'Order Updates']))
FREQUENCY_LOW_RISK, FREQUENCY_MEDIUM_RISK, FREQUENCY_HIGH_RISK = 5, 3, 0
STANDARD_BUNDLE_VOLUME = 6


def default_preferences():
    return {'muted_categories': [], 'daily_cap': 2, 'weekly_cap': 5, 'quiet_start': 22, 'quiet_end': 8, 'timezone': 'Asia/Kolkata', 'promotional_opt_out': False, 'disable_all': False, 'recovery_probes': False, 'probe_interval_weeks': 4, 'max_probes_per_week': 1}


def calculate_notification_engagement(n):
    if n.get('action') != 'opened': return 0.0
    return min(1.0, .5 + .3 * bool(n.get('clicked')) + .2 * bool(n.get('saved')))


class PolicyEngine:
    def __init__(self, model_path=None):
        self.model, self.metadata, self.error = None, {}, None
        try:
            if not model_path: raise ValueError('No model configured. Run python run.py --prepare.')
            bundle = joblib.load(model_path)
            self.metadata = bundle['metadata']
            if self.metadata['schema_version'] != 2 or self.metadata['feature_schema'] != FEATURE_COLUMNS:
                raise ValueError('Incompatible feature schema; run python run.py --prepare.')
            self.model = bundle['model']
        except Exception as exc:
            self.error = f'Model unavailable: {exc}. Run python run.py --prepare to rebuild trusted local artifacts.'

    def analyze_customer(self, customer_id, name, history, is_unsubscribed=False, preferences=None):
        prefs = default_preferences() | (preferences or {})
        events = history_events(history)
        if preferences is None:
            prefs['muted_categories'] = sorted({e['notification_type'] for e in events if e['muted_type'] and e['notification_type'] in PROMO_TYPES})
        snapshot = max((h['week'] for h in history), default=0) * 7
        recent = [e for e in events if snapshot-21 <= e['day'] < snapshot]
        features = extract_live_features(history)
        enough = len(recent) >= 6 and len(history) >= 3
        unsub = bool(is_unsubscribed or prefs['promotional_opt_out'])
        error, probability = self.error, None
        if self.model is not None and enough and not unsub and not prefs['disable_all']:
            try:
                probability = float(self.model.predict_proba(pd.DataFrame([features])[FEATURE_COLUMNS])[0, list(self.model.classes_).index(1)])
            except Exception as exc:
                error = f'Inference failed: {exc}. Rebuild the model with python run.py --prepare.'
        threshold = self.metadata.get('validation_thresholds', {'medium': .3, 'high': .6})
        model_tier = 'Unavailable' if probability is None else ('High' if probability >= threshold['high'] else 'Medium' if probability >= threshold['medium'] else 'Low')
        week_rates = []
        for h in sorted(history, key=lambda h: h['week']):
            ns = h.get('notifications', [])
            week_rates.append(sum(n.get('action') == 'opened' for n in ns)/len(ns) if ns else 0)
        promo_rates = []
        for h in sorted(history, key=lambda h: h['week']):
            ns = [n for n in h.get('notifications', []) if n['type'] in PROMO_TYPES]
            promo_rates.append(sum(n.get('action') == 'opened' for n in ns)/len(ns) if ns else None)
        rolling = promo_rates[-5:]
        earlier = [r for r in rolling[:2] if r is not None]
        latest = [r for r in rolling[-2:] if r is not None]
        difference = sum(latest)/len(latest)-sum(earlier)/len(earlier) if earlier and latest else 0
        trend = 'Insufficient history' if len(history)<3 else 'Insufficient promotional exposure' if not latest or not earlier else 'Recovering' if difference>.25 else 'Declining' if difference<-.25 else 'Inactive' if sum(latest)/len(latest)<.1 else 'Steady'
        # Explicit rule override is visible; it is never represented as an ML probability.
        rule_high = enough and features['open_rate_21d'] < .1
        policy_tier = 'High' if model_tier == 'High' or rule_high else 'Medium' if model_tier == 'Medium' or trend == 'Declining' else 'Low'
        overrides = ['Observed 21-day open rate below 10%: conservative promotional suppression.'] if rule_high else []
        interests, continued, paused = {}, [], []
        for category in ALL_TYPES:
            ns = [e for e in recent if e['notification_type']==category]
            score = sum(e['action']=='opened' for e in ns)/len(ns) if ns else .5
            streak = 0
            for e in reversed(ns):
                if e['action']=='opened': break
                streak += 1
            explicit = category in prefs['muted_categories']
            interests[category] = {'score': round(score,3), 'level': 'Unknown' if not ns else 'High' if score>=.55 else 'Medium' if score>=.25 else 'Low', 'display_name': TYPE_DISPLAY_NAMES[category], 'muted': explicit, 'ignore_streak': streak, 'exposures': len(ns)}
            reason = None
            if prefs['disable_all']: reason = 'Explicit disable-all preference'
            elif category != 'order_update':
                if unsub: reason = 'Explicit promotional opt-out'
                elif explicit: reason = 'Explicit category mute'
                elif policy_tier == 'High': reason = 'High policy risk: promotional suppression; no recovery probes'
                elif len(ns)>=3 and (score<.25 or streak>=3): reason = 'Automatic low-interest pause based on recent behavior'
            item = {'type': category, 'name': TYPE_DISPLAY_NAMES[category], 'score': score, 'reason': reason or ('Only from an order lifecycle event' if category=='order_update' else 'Eligible under policy and preferences')}
            (paused if reason else continued).append(item)
        eligible_categories = sum(item['type'] in PROMO_TYPES for item in continued)
        frequency = 0 if unsub or prefs['disable_all'] else min(prefs['weekly_cap'], 0 if policy_tier=='High' else 3 if policy_tier=='Medium' else 5, 2 * eligible_categories)
        overrides.append(f'Category relevance budget: two weekly slots per eligible promotional category ({eligible_categories}); tier and explicit caps may reduce this further.')
        status = 'disabled' if prefs['disable_all'] else 'unsubscribed' if unsub else 'insufficient_history' if not enough else 'at_risk' if policy_tier=='High' else 'losing_interest' if policy_tier=='Medium' else 'engaged'
        observations = [f"Recent 21 days: {sum(e['action']=='opened' for e in recent)} opened / {len(recent)} delivered notifications.", f"Recent click count: {sum(e['clicked'] for e in recent)}; save count: {sum(e['saved'] for e in recent)}.", f'{len(history)} completed simulation weeks. Durations are simulated.']
        explanation = {'kind': 'unavailable', 'values': {}}
        if probability is not None:
            estimator = self.model.steps[-1][1] if hasattr(self.model, 'steps') else self.model
            if hasattr(estimator, 'coef_'):
                scaled = self.model.steps[0][1].transform(pd.DataFrame([features])[FEATURE_COLUMNS])[0]
                explanation = {'kind': 'Local standardized logistic log-odds contributions; intercept excluded; not causal', 'values': dict(zip(FEATURE_COLUMNS, (scaled*estimator.coef_[0]).tolist()))}
            elif hasattr(estimator, 'feature_importances_'):
                explanation = {'kind': 'Global tree importance; not an individual attribution', 'values': dict(zip(FEATURE_COLUMNS, estimator.feature_importances_.tolist()))}
            else:
                explanation['kind'] = 'No feature attribution for KNN/prior baseline; observed evidence is separate'
        return {'customer_id': customer_id, 'name': name, 'status': status, 'status_label': status.replace('_',' ').title(), 'risk_level': policy_tier, 'model_risk_tier': model_tier, 'model_probability': probability, 'model_available': self.model is not None and not error, 'model_error': error, 'prediction_status': 'Available (uncalibrated)' if probability is not None else 'Promotional opt-out / disabled' if unsub or prefs['disable_all'] else 'Insufficient history: need 3 weeks and 6 recent events' if not enough else 'Rule-only fallback: model unavailable', 'policy_overrides': overrides, 'trend': trend, 'top_interest': max(interests, key=lambda t: interests[t]['score']), 'interests': interests, 'week_engagements': week_rates, 'features': features, 'model_explanation': explanation, 'likely_behavior': 'Estimate concerns future promotional disengagement, not shopping churn or psychological fatigue.', 'observations': observations, 'continued_types': continued, 'paused_types': paused, 'frequency': frequency, 'avoided_notifications': 0, 'recommended_action': 'Pause promotions' if policy_tier=='High' else 'Respect preferences and frequency caps', 'is_unsubscribed': unsub}
