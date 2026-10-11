"""SQLite sessions plus queryable event, preference, prediction and decision records."""
import json
import os
import sqlite3
from pathlib import Path
DB_PATH = Path(os.environ.get('SHOPEASY_DB', Path(__file__).resolve().parents[1] / 'data' / 'shopeasy.sqlite3'))


def connect():
    # FastAPI can resume a synchronous generator dependency on another worker.
    # Each request still owns this connection and serializes its transaction.
    db = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    for table in ['customers', 'events', 'preferences', 'predictions', 'decisions', 'orders']:
        db.execute(f'CREATE TABLE IF NOT EXISTS {table} (session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(session_id,id))')
    db.commit()
    return db


def save(db, sid, state):
    old = db.execute('SELECT payload FROM sessions WHERE id=?', (sid,)).fetchone()
    if old and json.loads(old[0]).get('revision') != state.get('revision'):
        for table in ['customers', 'events', 'preferences', 'predictions', 'decisions', 'orders']:
            db.execute(f'DELETE FROM {table} WHERE session_id=?', (sid,))
    db.execute('INSERT INTO sessions VALUES (?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (sid, json.dumps(state)))
    for cid, c in state['customers'].items():
        for table, key, payload in [('customers', cid, c), ('preferences', cid, c['preferences'])]:
            db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?)', (sid, key, json.dumps(payload)))
        for h in c['history']:
            for e in h['notifications']:
                db.execute('INSERT OR REPLACE INTO events VALUES (?,?,?)', (sid, e['id'], json.dumps(e)))
                if e.get('order_event'):
                    db.execute('INSERT OR REPLACE INTO orders VALUES (?,?,?)', (sid, e['order_event_id'], json.dumps(e['order_event'])))
        for e in c.get('subscription_events', []):
            db.execute('INSERT OR REPLACE INTO events VALUES (?,?,?)', (sid, e['id'], json.dumps(e)))
        for log in c.get('decision_history', []):
            db.execute('INSERT OR REPLACE INTO predictions VALUES (?,?,?)', (sid, log['id'], json.dumps(log['prediction'])))
            for decision in log['decisions']:
                db.execute('INSERT OR REPLACE INTO decisions VALUES (?,?,?)', (sid, log['id'] + ':' + decision['id'], json.dumps(decision)))
