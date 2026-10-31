"""Durable score/practice sessions. Each accepted action is one SQLite transaction.

No community wallet is kept here. Callers mutate a detached JSON snapshot, then
render the committed result; stale controls can never draw again or score twice.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from contextlib import contextmanager
from typing import Callable


class SessionStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, guild TEXT NOT NULL, owner TEXT NOT NULL,
                    kind TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL, state TEXT NOT NULL, updated REAL NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_run
                    ON sessions(guild, owner, kind) WHERE status != 'finished';
                CREATE TABLE IF NOT EXISTS records (
                    session_id TEXT PRIMARY KEY, guild TEXT NOT NULL,
                    owner TEXT NOT NULL, kind TEXT NOT NULL, score INTEGER NOT NULL,
                    reason TEXT NOT NULL, finished REAL NOT NULL
                );
            ''')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        result = dict(row)
        result['state'] = json.loads(result['state'])
        return result

    def get(self, session_id):
        with self._connect() as db:
            return self._decode(db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone())

    def active(self, guild, owner, kind):
        with self._connect() as db:
            return self._decode(db.execute(
                "SELECT * FROM sessions WHERE guild=? AND owner=? AND kind=? AND status!='finished'",
                (str(guild), str(owner), kind)).fetchone())

    def create(self, guild, owner, kind, state):
        """Return an existing unfinished run instead of silently replacing it."""
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute(
                "SELECT * FROM sessions WHERE guild=? AND owner=? AND kind=? AND status!='finished'",
                (str(guild), str(owner), kind)).fetchone()
            if existing:
                return self._decode(existing)
            session_id = uuid.uuid4().hex
            db.execute('INSERT INTO sessions VALUES (?, ?, ?, ?, 0, ?, ?, ?)',
                       (session_id, str(guild), str(owner), kind, 'active', json.dumps(state), time.time()))
            return self._decode(db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone())

    def apply(self, session_id, revision, actor, update: Callable, *, authorize=None):
        """Return (saved snapshot, applied). Callback errors roll back everything.

        update(snapshot) may set status='paused'/'finished' and record={score,reason}.
        Multiplayer callers provide an authorization function evaluated under lock.
        """
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            snapshot = self._decode(db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone())
            if snapshot is None:
                raise ValueError('This saved table no longer exists.')
            allowed = authorize(snapshot, str(actor)) if authorize else snapshot['owner'] == str(actor)
            if not allowed:
                raise PermissionError('This is another player\'s table.')
            if snapshot['revision'] != revision or snapshot['status'] == 'finished':
                return snapshot, False
            update(snapshot)
            status = snapshot['status']
            if status not in ('active', 'paused', 'finished'):
                raise ValueError('Invalid session status')
            snapshot['revision'] += 1
            snapshot['updated'] = time.time()
            encoded = json.dumps(snapshot['state'], allow_nan=False)
            db.execute('UPDATE sessions SET revision=?, status=?, state=?, updated=? WHERE id=?',
                       (snapshot['revision'], status, encoded, snapshot['updated'], session_id))
            if status == 'finished' and 'record' in snapshot:
                record = snapshot.pop('record')
                db.execute('INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (session_id, snapshot['guild'], snapshot['owner'], snapshot['kind'],
                            int(record['score']), record['reason'], snapshot['updated']))
            return snapshot, True

    def records(self, guild, owner, kind, limit=10):
        with self._connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM records WHERE guild=? AND owner=? AND kind=? ORDER BY score DESC, finished DESC LIMIT ?',
                (str(guild), str(owner), kind, min(25, max(1, limit))))]
