"""One candidate stream, two transparent schedules. No counterfactual responses."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from ml.features import EPOCH
from engine.policy import PROMO_TYPES


def quiet_time(dt, start, end):
    if start == end: return False
    return dt.hour >= start or dt.hour < end if start > end else start <= dt.hour < end


def schedule(candidates, analysis, prefs, week, adaptive=True):
    zone = ZoneInfo(prefs['timezone'])
    week_end = EPOCH + timedelta(days=week*7)
    daily, weekly, probes = {}, 0, 0
    paused = {p['type']: p['reason'] for p in analysis['paused_types']}
    decisions = []
    seen = set()
    for candidate in sorted(candidates, key=lambda c: (c['timestamp'], c['id'])):
        if candidate['id'] in seen: continue
        seen.add(candidate['id'])
        n = dict(candidate)
        n.update(status='allowed', reason='Baseline candidate; explicit preferences and caps respected' if not adaptive else 'Eligible under adaptive policy', is_recheck=False)
        category = n['type']
        reason = None
        if prefs['disable_all']: reason = 'Explicit disable-all preference'
        elif category == 'order_update':
            if not n.get('order_event_id'): reason = 'Missing order lifecycle event'
        elif prefs['promotional_opt_out']: reason = 'Explicit promotional opt-out'
        elif category in prefs['muted_categories']: reason = 'Explicit category mute; probes prohibited'
        elif adaptive and category in paused:
            reason = paused[category]
            eligible = reason.startswith('Automatic') and prefs['recovery_probes'] and analysis['risk_level'] != 'High' and week % prefs['probe_interval_weeks'] == 0 and probes < prefs['max_probes_per_week']
            if eligible:
                probes += 1
                reason = None
                n.update(is_recheck=True, reason='Limited recovery probe: automatic pause, enabled, interval due, within promotional caps')
        if reason:
            n.update(status='suppressed', reason=reason, scheduled_at=None)
        elif category == 'order_update':
            n.update(reason='Transactional: simulated order lifecycle; bypasses promotional caps and quiet hours', scheduled_at=n['timestamp'])
        else:
            limit = min(prefs['weekly_cap'], analysis['frequency']) if adaptive else prefs['weekly_cap']
            dt = datetime.fromisoformat(n['timestamp']).astimezone(zone)
            original = dt
            while dt.astimezone(EPOCH.tzinfo) < week_end:
                date = dt.date().isoformat()
                if weekly >= limit or prefs['daily_cap'] == 0:
                    break
                if quiet_time(dt, prefs['quiet_start'], prefs['quiet_end']):
                    dt += timedelta(hours=1)
                    dt = dt.replace(minute=0, second=0)
                    continue
                if daily.get(date,0) >= prefs['daily_cap']:
                    dt = (dt+timedelta(days=1)).replace(hour=0, minute=0, second=0)
                    continue
                break
            date = dt.date().isoformat()
            if weekly >= limit or prefs['daily_cap']==0 or dt.astimezone(EPOCH.tzinfo)>=week_end:
                n.update(status='deferred', reason='Promotional cap or period boundary: reconsider next week; not delivered', scheduled_at=None)
            else:
                weekly += 1
                daily[date] = daily.get(date,0)+1
                n['scheduled_at'] = dt.isoformat()
                if dt != original:
                    n.update(status='deferred', reason='Moved to an eligible time for quiet hours / daily cap; scheduled this week')
        decisions.append(n)
    return decisions


def comparison(baseline, adaptive, history):
    def counts(plan):
        return {status: sum(n['type'] in PROMO_TYPES and n['status']==status for n in plan) for status in ['allowed','deferred','suppressed']}
    observed = [n for h in history for n in h['notifications'] if n['type'] in PROMO_TYPES]
    return {'candidate_promotions': sum(n['type'] in PROMO_TYPES for n in baseline), 'baseline': counts(baseline), 'adaptive': counts(adaptive), 'observed': {'delivered_promotions': len(observed), 'opened_promotions': sum(n.get('action')=='opened' for n in observed), 'clicked_promotions': sum(bool(n.get('clicked')) for n in observed)}, 'note': 'Same upcoming candidates and week. Baseline respects explicit preferences. Observed metrics describe delivered simulated history only. No responses imputed to suppressed candidates or causal retention claims.'}
