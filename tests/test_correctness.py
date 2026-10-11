"""Correctness contracts, persistence, API validation and end-to-end simulation tests."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ml.features import EPOCH, FEATURE_COLUMNS, history_events, extract_live_features, extract_snapshot_features_from_events, normalize_event
from ml.train_model import future_label, build_snapshots, HORIZON, SPLITS, fingerprint
from engine.policy import PolicyEngine, default_preferences, PROMO_TYPES
from engine.scenarios import generate_week_notifications
from engine.planner import quiet_time, schedule, comparison
from engine import storage


def history(weeks, action='opened'):
    result=[]
    for week in weeks:
        notifications=generate_week_notifications('guest',week)
        for n in notifications: n.update(action=action,duration='read_fully',clicked=action=='opened')
        result.append({'week':week,'notifications':notifications})
    return result


def test_labels_censor_absent_exposure_and_incomplete_followup():
    assert future_label([],[],21,210) is None
    assert future_label([],[],203,210) is None
    assert future_label([], [{'day':22}],21,210)==1
    assert future_label([], [{'day':204}],203,210) is None
    events=[{'day':22+i,'notification_type':'offer','action':'ignored'} for i in range(5)]
    assert future_label(events,[],21,210)==1
    events[0]['action']='opened'
    assert future_label(events,[],21,210)==0
    assert future_label(events[:4],[],21,210) is None


def test_unsubscribe_recording_and_chart_source():
    subs=pd.read_csv(ROOT/'data/subscription_events.csv')
    notifs=pd.read_csv(ROOT/'data/notifications.csv')
    assert len(subs)>0
    for row in subs.to_dict('records'):
        assert datetime.fromisoformat(row['timestamp'])==EPOCH+timedelta(days=row['day'])
        assert not ((notifs.customer_id==row['customer_id']) & (notifs.day>=row['day'])).any()
    meta=json.loads((ROOT/'data/dataset_metadata.json').read_text())
    assert len(subs)==meta['subscription_events']
    assert (ROOT/'reports/unsubscribed_over_time.png').stat().st_size>1000


def test_generator_persists_subscription_before_stopping(tmp_path):
    from data.generate_data import generate_dataset
    data, reports = tmp_path/'data', tmp_path/'reports'
    generate_dataset(data, reports, total_customers=50, total_days=60)
    subs = pd.read_csv(data/'subscription_events.csv')
    events = pd.read_csv(data/'notifications.csv')
    assert len(subs)>0
    for sub in subs.to_dict('records'):
        assert not ((events.customer_id==sub['customer_id']) & (events.day>=sub['day'])).any()
    orders = pd.read_csv(data/'order_events.csv')
    transactions = events[events.notification_type=='order_update']
    assert set(transactions.order_event_id)==set(orders.id)
    assert len(transactions)==len(orders)


def test_mute_flag_and_action_share_schema():
    n=generate_week_notifications('guest',1)[0]
    offline=normalize_event(dict(n,action='dismissed',muted_type=1))
    live=normalize_event(dict(n,action='muted'))
    assert offline['action']==live['action']=='muted'
    assert offline['muted_type']==live['muted_type']==1


@pytest.fixture(scope='module')
def snapshots(): return build_snapshots(ROOT/'data')


def test_exclude_prior_unsubscribe_and_purge(snapshots):
    subs=pd.read_csv(ROOT/'data/subscription_events.csv')
    merged=snapshots.merge(subs[['customer_id','day']],on='customer_id')
    assert (merged.snapshot_day<=merged.day).all()
    assert SPLITS['train'][1]+HORIZON<SPLITS['validation'][0]
    assert SPLITS['validation'][1]+HORIZON<SPLITS['test'][0]
    meta=json.loads((ROOT/'models/metadata.json').read_text())
    assert meta['dataset_fingerprint']==fingerprint(ROOT/'data')
    assert meta['feature_schema']==FEATURE_COLUMNS
    assert not any('persona' in col or 'future' in col for col in FEATURE_COLUMNS)


def test_features_ignore_future_and_sort_order():
    events=history_events(history([1,2,3]))
    reference=extract_snapshot_features_from_events(events,21)
    future=normalize_event(dict(generate_week_notifications('guest',4)[0],action='muted'))
    assert reference==extract_snapshot_features_from_events([future]+list(reversed(events)),21)


def test_offline_live_consistency_and_simulated_duration():
    h=history([1,2,3])
    assert extract_live_features(h)==extract_snapshot_features_from_events(history_events(h),21)
    assert extract_live_features(h)['avg_view_seconds']==25
    assert all(n['duration_source']=='simulated' for w in h for n in w['notifications'])


def test_after_week_five_changes_interest_and_features():
    engine=PolicyEngine(ROOT/'models/risk_model.joblib')
    a=engine.analyze_customer('guest','Guest',history([1,2,3,4,5],'ignored'))
    b=engine.analyze_customer('guest','Guest',history([1,2,3,4,5],'ignored')+history([6,7,8]))
    assert a['features']['open_rate_21d']==0
    assert b['features']['open_rate_21d']==1
    assert b['interests']['offer']['score']==1
    assert b['risk_level']=='Low'


def test_model_missing_and_insufficient_history_are_explicit():
    engine=PolicyEngine(ROOT/'models/not-present.joblib')
    a=engine.analyze_customer('guest','Guest',history([1,2,3]))
    assert a['model_probability'] is None
    assert not a['model_available']
    assert 'Rule-only' in a['prediction_status']
    available=PolicyEngine(ROOT/'models/risk_model.joblib')
    for h in [[],history([1])]:
        a=available.analyze_customer('guest','Guest',h)
        assert a['model_probability'] is None
        assert a['status']=='insufficient_history'


def test_inference_failure_does_not_fabricate_probability():
    class Broken:
        def predict_proba(self, features): raise RuntimeError('broken artifact')
    engine=PolicyEngine(ROOT/'models/risk_model.joblib')
    engine.model=Broken()
    a=engine.analyze_customer('guest','Guest',history([1,2,3]))
    assert a['model_probability'] is None
    assert 'broken artifact' in a['model_error']
    assert not a['model_available']


def policy_context(week=4):
    prefs=default_preferences()
    engine=PolicyEngine(ROOT/'models/risk_model.joblib')
    analysis=engine.analyze_customer('guest','Guest',history([1,2,3]),False,prefs)
    return prefs,analysis,generate_week_notifications('guest',week)


def test_explicit_mutes_and_high_risk_never_probe():
    prefs,a,candidates=policy_context()
    prefs.update(recovery_probes=True,muted_categories=PROMO_TYPES)
    plan=schedule(candidates,a,prefs,4)
    assert all(n['status']=='suppressed' and not n['is_recheck'] for n in plan if n['type'] in PROMO_TYPES)
    prefs['muted_categories']=[]
    a['risk_level']='High'
    a['paused_types']=[{'type':t,'reason':'Automatic low-interest pause'} for t in PROMO_TYPES]
    plan=schedule(candidates,a,prefs,4)
    assert not any(n['is_recheck'] for n in plan)


def test_probes_limited_configurable_and_under_caps():
    prefs,a,candidates=policy_context()
    prefs.update(recovery_probes=True)
    a['paused_types']=[{'type':t,'reason':'Automatic low-interest pause'} for t in PROMO_TYPES]
    a['risk_level']='Low'
    assert sum(n['is_recheck'] for n in schedule(candidates,a,prefs,4))==1
    assert not any(n['is_recheck'] for n in schedule(generate_week_notifications('guest',5),a,prefs,5))
    prefs['weekly_cap']=0
    assert not any(n['scheduled_at'] for n in schedule(candidates,a,prefs,4) if n['type'] in PROMO_TYPES)


def test_optout_and_disable_all_and_transactional_provenance():
    prefs,a,candidates=policy_context()
    prefs['promotional_opt_out']=True
    plan=schedule(candidates,a,prefs,4)
    assert all(n['status']=='suppressed' for n in plan if n['type'] in PROMO_TYPES)
    assert all(n['scheduled_at'] for n in plan if n['type']=='order_update')
    candidates[3]['order_event_id']=None
    assert schedule(candidates,a,prefs,4)[3]['status']=='suppressed'
    prefs['disable_all']=True
    assert all(n['status']=='suppressed' for n in schedule(candidates,a,prefs,4))
    analysis=PolicyEngine(ROOT/'models/risk_model.joblib').analyze_customer('guest','Guest',history([1,2,3]),False,prefs)
    assert analysis['status']=='disabled'
    assert analysis['model_probability'] is None


def test_quiet_hours_cross_midnight_and_daily_weekly_caps():
    for hour,expected in [(23,True),(1,True),(7,True),(8,False),(21,False)]:
        assert quiet_time(EPOCH.replace(hour=hour),22,8)==expected
    assert not quiet_time(EPOCH,0,0)
    prefs,a,candidates=policy_context()
    prefs.update(timezone='UTC',daily_cap=1,weekly_cap=2)
    for n in candidates: n['timestamp']=(EPOCH+timedelta(days=21,hours=23)).isoformat()
    plan=schedule(candidates,a,prefs,4)
    delivered=[n for n in plan if n['type'] in PROMO_TYPES and n['scheduled_at']]
    assert len(delivered)==2
    assert len({datetime.fromisoformat(n['scheduled_at']).date() for n in delivered})==2
    assert all(not quiet_time(datetime.fromisoformat(n['scheduled_at']),22,8) for n in delivered)


def test_fair_baseline_same_ids_and_denominators_no_duplicates():
    prefs,a,candidates=policy_context()
    baseline=schedule(candidates,a,prefs,4,False)
    adaptive=schedule(candidates+[candidates[0]],a,prefs,4)
    assert {n['id'] for n in baseline}=={n['id'] for n in adaptive}
    summary=comparison(baseline,adaptive,history([1,2,3]))
    assert sum(summary['baseline'].values())==sum(summary['adaptive'].values())==summary['candidate_promotions']
    assert summary['observed']['delivered_promotions']==15


def test_storage_restart_and_scoped_reset(tmp_path,monkeypatch):
    from app import create_initial_state
    monkeypatch.setattr(storage,'DB_PATH',tmp_path/'db.sqlite3')
    a,b=str(uuid.uuid4()),str(uuid.uuid4())
    state=create_initial_state()
    state['customers']['guest']['history']=history([1])
    db=storage.connect()
    storage.save(db,a,state)
    storage.save(db,b,create_initial_state())
    db.commit();db.close()
    db=storage.connect()
    loaded=json.loads(db.execute('SELECT payload FROM sessions WHERE id=?',(a,)).fetchone()[0])
    assert len(loaded['customers']['guest']['history'])==1
    assert db.execute('SELECT count(*) FROM events WHERE session_id=?',(a,)).fetchone()[0]==6
    storage.save(db,a,create_initial_state());db.commit()
    assert db.execute('SELECT count(*) FROM events WHERE session_id=?',(a,)).fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM sessions WHERE id=?',(b,)).fetchone()[0]==1
    db.close()


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=os.environ.copy();env['SHOPEASY_DB']=str(tmp_path_factory.mktemp('api')/'test.sqlite3')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    url=f'http://127.0.0.1:{port}'
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(url+'/api/health',timeout=1).close();break
            except Exception: time.sleep(.1)
        else: raise AssertionError('Test server did not become healthy')
        yield url
    finally:
        process.terminate();process.wait(timeout=10)


def request(server,sid,path,method='GET',body=None):
    req=urllib.request.Request(server+'/api/'+path,data=None if body is None else json.dumps(body).encode(),method=method,headers={'Content-Type':'application/json','X-Simulation-ID':sid})
    try:
        with urllib.request.urlopen(req,timeout=10) as response: return response.status,json.load(response)
    except urllib.error.HTTPError as exc: return exc.code,json.load(exc)


def test_api_persistence_isolation_idempotency_validation(server):
    a,b=str(uuid.uuid4()),str(uuid.uuid4())
    s=request(server,a,'state')[1]
    request(server,a,'customer/guest/select','POST')
    c=request(server,a,'state')[1]['selected_customer']
    payload={'submission_id':str(uuid.uuid4()),'week':1,'actions':[{'id':n['id'],'action':'opened','clicked':True} for n in c['active_week_notifications']]}
    assert request(server,a,'customer/guest/submit-week','POST',payload)[0]==200
    assert request(server,a,'customer/guest/submit-week','POST',payload)[1]['duplicate']
    after=request(server,a,'state')[1]['selected_customer']
    assert after['current_week']==2 and len(after['history'])==1
    assert request(server,b,'state')[1]['selected_customer']['id']=='aarav'
    assert request(server,b,'state')[1]['selected_customer']['current_week']==1
    bad={**payload,'submission_id':str(uuid.uuid4())}
    assert request(server,a,'customer/guest/submit-week','POST',bad)[0]==409
    bad={**bad,'week':2,'actions':[{'id':'bad','action':'hacked'}]}
    assert request(server,a,'customer/guest/submit-week','POST',bad)[0]==422
    bad['actions']=[{'id':'bad','action':'opened'}]
    assert request(server,a,'customer/guest/submit-week','POST',bad)[0]==422
    prefs={**after['preferences'],'daily_cap':-1}
    assert request(server,a,'customer/guest/preferences','PUT',prefs)[0]==422
    prefs={**after['preferences'],'timezone':'Not/AZone'}
    assert request(server,a,'customer/guest/preferences','PUT',prefs)[0]==422
    request(server,a,'reset','POST')
    assert request(server,a,'state')[1]['selected_customer']['current_week']==1
    assert request(server,b,'state')[1]['selected_customer']['id']=='aarav'


def test_api_immediate_unsubscribe_and_progress_beyond_five(server):
    sid=str(uuid.uuid4())
    request(server,sid,'customer/guest/select','POST')
    c=request(server,sid,'state')[1]['selected_customer']
    actions=[{'id':n['id'],'action':'unsubscribed' if i==0 else 'ignored'} for i,n in enumerate(c['active_week_notifications'])]
    payload={'submission_id':str(uuid.uuid4()),'week':1,'actions':actions}
    assert request(server,sid,'customer/guest/submit-week','POST',payload)[0]==200
    c=request(server,sid,'state')[1]['selected_customer']
    assert c['preferences']['promotional_opt_out']
    assert all(n['type']=='order_update' for n in c['active_week_notifications'])
    assert len(c['subscription_events'])==1
    assert len(c['history'][0]['notifications'])==2  # opt-out event plus later order lifecycle
    for _ in range(6): assert request(server,sid,'customer/guest/auto-play','POST')[0]==200
    c=request(server,sid,'state')[1]['selected_customer']
    assert c['current_week']==8
    assert len(c['decision_history'])==7


def test_complete_api_demo_and_assets(server):
    sid=str(uuid.uuid4())
    assert request(server,sid,'sample-behaviour','POST')[0]==200
    assert request(server,sid,'run-system','POST')[0]==200
    s=request(server,sid,'state')[1]
    assert all(c['current_week']==6 for c in s['customers'] if c['id']!='guest')
    request(server,sid,'customer/meera/select','POST')
    meera=request(server,sid,'state')[1]['selected_customer']
    assert meera['history'][3]['delivery_policy']=='baseline_observation'
    assert any(n['type']=='offer' and n['action']=='opened' for n in meera['history'][3]['notifications'])
    assert request(server,sid,'evaluation')[1]['selected_test']['confusion_matrix']
    for path in ['/','/static/app.js','/static/style.css','/reports/evaluation.png']:
        with urllib.request.urlopen(server+path) as response: assert response.status==200


def test_concurrent_sessions_and_duplicate_submission(server):
    sid=str(uuid.uuid4())
    request(server,sid,'customer/guest/select','POST')
    c=request(server,sid,'state')[1]['selected_customer']
    body={'submission_id':str(uuid.uuid4()),'week':1,'actions':[{'id':n['id'],'action':'opened'} for n in c['active_week_notifications']]}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(request,server,sid,'customer/guest/submit-week','POST',body) for _ in range(3)]
        futures += [pool.submit(request,server,str(uuid.uuid4()),'state') for _ in range(3)]
        assert all(f.result()[0]==200 for f in futures)
    c=request(server,sid,'state')[1]['selected_customer']
    assert c['current_week']==2
    assert len(c['history'])==1


def test_active_delivery_order_uses_absolute_scheduled_time():
    from app import init_customer_state, refresh
    c=init_customer_state({'id':'guest','name':'Guest'})
    c['preferences'].update(timezone='Asia/Kolkata',daily_cap=1,quiet_start=20,quiet_end=10)
    refresh(c)
    stamps=[datetime.fromisoformat(n['timestamp']) for n in c['active_week_notifications']]
    assert stamps==sorted(stamps)


def test_direct_pdf_report_is_customer_scoped_and_does_not_advance(server):
    sid=str(uuid.uuid4())
    request(server,sid,'customer/ishita/select','POST')
    before=request(server,sid,'state')[1]['selected_customer']
    req=urllib.request.Request(server+'/api/customer/ishita/report.pdf',headers={'X-Simulation-ID':sid})
    with urllib.request.urlopen(req) as response:
        pdf=response.read()
        assert response.headers['Content-Type']=='application/pdf'
        assert response.headers['Content-Disposition']=='attachment; filename="shopeasy-ishita-week-1-report.pdf"'
        assert response.headers['Cache-Control']=='no-store'
        assert pdf.startswith(b'%PDF-') and b'%%EOF' in pdf
        assert b'Ishita' in pdf
    after=request(server,sid,'state')[1]['selected_customer']
    assert after==before
    req=urllib.request.Request(server+'/api/customer/not-a-customer/report.pdf',headers={'X-Simulation-ID':sid})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code==404
