"""Session-scoped persistent demonstration API. All simulation outcomes are synthetic."""
from pathlib import Path
import json
import uuid
import sqlite3
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict, field_validator
from engine.scenarios import CUSTOMERS, generate_week_notifications, get_scripted_action_for_customer
from engine.policy import PolicyEngine, default_preferences, PROMO_TYPES
from engine.planner import schedule, comparison
from engine import storage
from ml.features import EPOCH, normalize_event
BASE = Path(__file__).resolve().parent
app = FastAPI(title='ShopEasy Smart Notifications', version='2.0')
policy_engine = PolicyEngine(BASE / 'models/risk_model.joblib')


@app.exception_handler(sqlite3.Error)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': f'SQLite could not save/load this simulation: {exc}. Check data directory permissions, disk space, and retry.'})


def init_customer_state(meta):
    return {**meta, 'current_week': 1, 'is_finished': False, 'is_unsubscribed': False, 'history': [], 'subscription_events': [], 'preferences': default_preferences(), 'analysis': None, 'planner': [], 'baseline': [], 'decision_history': [], 'submissions': {}, 'active_week_notifications': generate_week_notifications(meta['id'], 1)}


def create_initial_state():
    state = {'revision': uuid.uuid4().hex, 'customers': {m['id']: init_customer_state(m) for m in CUSTOMERS}, 'selected_customer_id': 'aarav', 'system_run': False}
    for c in state['customers'].values(): refresh(c, audit=False)
    return state


def refresh(c, audit=True):
    c['is_unsubscribed'] = c['preferences']['promotional_opt_out']
    c['analysis'] = policy_engine.analyze_customer(c['id'], c['name'], c['history'], c['is_unsubscribed'], c['preferences'])
    candidates = generate_week_notifications(c['id'], c['current_week'])
    c['planner'] = schedule(candidates, c['analysis'], c['preferences'], c['current_week'])
    c['baseline'] = schedule(candidates, c['analysis'], c['preferences'], c['current_week'], adaptive=False)
    c['comparison'] = comparison(c['baseline'], c['planner'], c['history'])
    c['active_week_notifications'] = sorted([dict(n, timestamp=n['scheduled_at']) for n in c['planner'] if n['scheduled_at']], key=lambda n: (datetime.fromisoformat(n['timestamp']), n['id']))
    c['continued_notifications'] = c['active_week_notifications']
    if audit:
        c['decision_history'].append({'id': uuid.uuid4().hex, 'week': c['current_week'], 'simulation_time': (EPOCH + timedelta(days=(c['current_week']-1)*7)).isoformat(), 'prediction': c['analysis'], 'preferences': dict(c['preferences']), 'decisions': c['planner']})


def session(request: Request, response: Response):
    sid = request.headers.get('X-Simulation-ID') or request.cookies.get('shopeasy_session')
    if sid:
        try: uuid.UUID(sid)
        except ValueError: raise HTTPException(422, 'Simulation ID must be a UUID')
    db = storage.connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM sessions WHERE id=?', (sid or '',)).fetchone()
        if row:
            state = json.loads(row[0])
        else:
            sid, state = sid or uuid.uuid4().hex, create_initial_state()
            response.set_cookie('shopeasy_session', sid, httponly=True, samesite='lax', max_age=31536000)
        yield state
        storage.save(db, sid, state)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def customer(state, cid):
    if cid not in state['customers']: raise HTTPException(404, 'Unknown customer')
    return state['customers'][cid]


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=100)
    action: Literal['opened','ignored','dismissed','muted','unsubscribed']
    duration: Literal['quick_glance','few_seconds','read_fully'] = 'few_seconds'
    timing: Literal['right_away','later_today','next_day'] = 'right_away'
    view_seconds: float | None = Field(default=None, ge=0, le=3600)
    clicked: bool = False
    saved: bool = False


class WeekSubmission(BaseModel):
    model_config = ConfigDict(extra='forbid')
    submission_id: str = Field(min_length=8, max_length=100)
    week: int = Field(ge=1, le=10000)
    actions: list[Action] = Field(max_length=100)


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid')
    muted_categories: list[Literal['offer','new_arrival','price_drop']] = Field(default_factory=list, max_length=3)
    daily_cap: int = Field(default=2, ge=0, le=20)
    weekly_cap: int = Field(default=5, ge=0, le=100)
    quiet_start: int = Field(default=22, ge=0, le=23)
    quiet_end: int = Field(default=8, ge=0, le=23)
    timezone: str = Field(default='Asia/Kolkata', max_length=100)
    promotional_opt_out: bool = False
    disable_all: bool = False
    recovery_probes: bool = False
    probe_interval_weeks: int = Field(default=4, ge=2, le=52)
    max_probes_per_week: int = Field(default=1, ge=0, le=1)

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, v):
        try: ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError): raise ValueError('Use a valid IANA timezone, e.g. Asia/Kolkata')
        return v


@app.get('/api/health')
def health():
    try:
        db = storage.connect()
        db.execute('SELECT 1')
        db.close()
    except Exception as exc: raise HTTPException(503, f'SQLite unavailable: {exc}. Check data directory permissions.')
    return {'status': 'ok', 'model_available': policy_engine.model is not None, 'model_error': policy_engine.error, 'synthetic': True}


@app.get('/api/state')
def get_state(state=Depends(session, scope="function")):
    selected = state['customers'][state['selected_customer_id']]
    return {**state, 'customers': [{k: c[k] for k in ['id','name','initials','role_hint','current_week','is_unsubscribed']} | {'status': c['analysis']['status'], 'status_label': c['analysis']['status_label'], 'frequency': c['analysis']['frequency']} for c in state['customers'].values()], 'selected_customer': selected, 'model_available': policy_engine.model is not None and selected['analysis']['model_available'], 'model_error': selected['analysis']['model_error'] or policy_engine.error, 'synthetic': True}


@app.post('/api/customer/{cid}/select')
def select(cid: str, state=Depends(session, scope="function")):
    customer(state, cid)
    state['selected_customer_id'] = cid
    return {'ok': True}


def apply_week(c, submission):
    payload = submission.model_dump(mode='json')
    key = submission.submission_id
    if key in c['submissions']:
        if c['submissions'][key] != payload: raise HTTPException(409, 'Submission ID reused with different actions')
        return {'ok': True, 'duplicate': True}
    if submission.week != c['current_week']: raise HTTPException(409, 'Stale week. Refresh before submitting.')
    actions = {a.id: a for a in submission.actions}
    available = {n['id'] for n in c['active_week_notifications']}
    if len(actions) != len(submission.actions): raise HTTPException(422, 'Duplicate notification IDs')
    if set(actions) != available: raise HTTPException(422, 'Submit exactly the delivered notification IDs for the active week')
    notifications = []
    for source in c['active_week_notifications']:
        n = dict(source)
        a = actions[n['id']].model_dump(exclude_none=True)
        if (a['clicked'] or a['saved']) and a['action'] != 'opened': raise HTTPException(422, 'Click/save requires an opened notification')
        # A preference change applies immediately to subsequent notifications in this batch.
        if c['preferences']['disable_all'] or (n['type'] in PROMO_TYPES and (c['preferences']['promotional_opt_out'] or n['type'] in c['preferences']['muted_categories'])):
            continue
        n.update(a)
        normalized = normalize_event(n)
        n.update(view_seconds=normalized['view_seconds'], muted_type=normalized['muted_type'], duration_source='simulated', event_id=n['id'])
        notifications.append(n)
        if n['action']=='muted':
            if n['type'] not in PROMO_TYPES: raise HTTPException(422, 'Only promotional categories can be muted')
            c['preferences']['muted_categories'] = sorted(set(c['preferences']['muted_categories'] + [n['type']]))
        if n['action']=='unsubscribed':
            c['preferences']['promotional_opt_out'] = True
            c['subscription_events'].append({'id': uuid.uuid4().hex, 'action': 'unsubscribed', 'scope': 'promotional', 'timestamp': n['timestamp']})
    c['history'].append({'week': c['current_week'], 'notifications': notifications})
    c['current_week'] += 1
    c['submissions'][key] = payload
    refresh(c)
    return {'ok': True, 'customer': c}


@app.post('/api/customer/{cid}/submit-week')
@app.post('/api/customer/{cid}/continue-act')
def submit(cid: str, submission: WeekSubmission, state=Depends(session, scope="function")):
    return apply_week(customer(state,cid), submission)


def scripted_week(c, baseline_observation=False):
    if baseline_observation:
        # The initial scripted observation phase precedes personalization.
        # Respect explicit preferences/caps; never invent responses to suppression.
        c['active_week_notifications'] = sorted([dict(n, timestamp=n['scheduled_at']) for n in c['baseline'] if n['scheduled_at']], key=lambda n: (datetime.fromisoformat(n['timestamp']), n['id']))
    actions = [Action(**({'id': n['id']} | get_scripted_action_for_customer(c['id'], c['current_week'], n))) for n in c['active_week_notifications']]
    result = apply_week(c, WeekSubmission(submission_id=uuid.uuid4().hex, week=c['current_week'], actions=actions))
    c['history'][-1]['delivery_policy'] = 'baseline_observation' if baseline_observation else 'adaptive'
    return result


@app.post('/api/customer/{cid}/auto-play')
def auto_play(cid: str, state=Depends(session, scope="function")):
    c = customer(state,cid)
    scripted_week(c)
    return {'ok': True, 'customer': c}


@app.post('/api/sample-behaviour')
def sample(state=Depends(session, scope="function")):
    for cid, c in state['customers'].items():
        if cid == 'guest': continue
        # Preserve earlier progress and preferences; advance to the five-week checkpoint.
        while c['current_week'] <= 5: scripted_week(c, baseline_observation=True)
    state['system_run'] = True
    return {'ok': True}


@app.post('/api/run-system')
def analyze(state=Depends(session, scope="function")):
    for c in state['customers'].values(): refresh(c)
    state['system_run'] = True
    return {'ok': True}


@app.put('/api/customer/{cid}/preferences')
def preferences(cid: str, body: Preferences, state=Depends(session, scope="function")):
    c = customer(state,cid)
    before = c['preferences']
    c['preferences'] = body.model_dump()
    c['subscription_events'].append({'id': uuid.uuid4().hex, 'action': 'preferences_changed', 'timestamp': (EPOCH+timedelta(days=(c['current_week']-1)*7)).isoformat(), 'before': before, 'after': c['preferences']})
    refresh(c)
    return {'ok': True}


@app.get('/api/customer/{cid}/report.pdf')
def report_pdf(cid: str, state=Depends(session, scope="function")):
    from engine.customer_report import customer_pdf
    c = customer(state, cid)
    return Response(content=customer_pdf(c), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="shopeasy-{c["id"]}-week-{c["current_week"]}-report.pdf"', 'Cache-Control': 'no-store'})


@app.get('/api/evaluation')
def evaluation():
    path = BASE / 'reports/evaluation.json'
    if not path.exists(): raise HTTPException(503, 'Evaluation missing. Run python run.py --prepare.')
    return json.loads(path.read_text(encoding='utf-8'))


@app.post('/api/reset')
def reset(state=Depends(session, scope="function")):
    state.clear()
    state.update(create_initial_state())
    return {'ok': True, 'message': 'Only this browser simulation was reset'}


app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')
app.mount('/reports', StaticFiles(directory=BASE / 'reports'), name='reports')
@app.get('/')
def index(): return FileResponse(BASE / 'static/index.html')

