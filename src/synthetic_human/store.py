from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

_encode_event = json.JSONEncoder(ensure_ascii=False, separators=(",", ":")).encode


class Store:
    def __init__(self, path: Path, readonly=False):
        self.path = path
        self.event_sink = None
        self._events = []
        self._last_flush = time.monotonic()
        if readonly:
            self.db = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=10
            )
            self.db.row_factory = sqlite3.Row
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA busy_timeout=10000;
            CREATE TABLE IF NOT EXISTS authority (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                owner TEXT NOT NULL, epoch INTEGER NOT NULL, lease TEXT,
                lease_until REAL NOT NULL DEFAULT 0, handoffs INTEGER NOT NULL DEFAULT 0,
                no_progress INTEGER NOT NULL DEFAULT 0, progress INTEGER NOT NULL DEFAULT 0);
            INSERT OR IGNORE INTO authority(singleton,owner,epoch) VALUES(1,'supervisor',0);
            CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL, version INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY, state TEXT NOT NULL, created REAL);
            CREATE TABLE IF NOT EXISTS actions(
                id TEXT PRIMARY KEY, body TEXT NOT NULL, status TEXT NOT NULL,
                result TEXT, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS handoffs(
                id TEXT PRIMARY KEY, body TEXT NOT NULL, status TEXT NOT NULL, updated REAL);
            CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, time REAL, kind TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS artifact_versions(
                path TEXT, version INTEGER, sha256 TEXT, created REAL,
                PRIMARY KEY(path,version));
        """)

    @contextmanager
    def transaction(self):
        self.flush_events()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        self.db.execute(
            """INSERT INTO kv VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,version=kv.version+1""",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    def checkpoint(self, state):
        identity = str(uuid4())
        self.db.execute("INSERT INTO checkpoints VALUES(?,?,?)", (identity, json.dumps(state), time.time()))
        return identity

    def event(self, kind, body):
        self._events.append((time.time(), kind, _encode_event(body)))
        high_frequency = kind in ("input.dispatched", "timing", "typing.plan")
        if not high_frequency or len(self._events) >= 64 or time.monotonic() - self._last_flush >= 0.25:
            self.flush_events()
        if self.event_sink:
            try:
                self.event_sink(kind, body)
            except OSError:
                pass  # A closed log pipe must not turn a saved GUI action into a retry.

    def flush_events(self):
        if not self._events:
            return
        owned_transaction = not self.db.in_transaction
        if owned_transaction:
            self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.executemany("INSERT INTO events(time,kind,body) VALUES(?,?,?)", self._events)
            if owned_transaction:
                self.db.execute("COMMIT")
        except BaseException:
            if owned_transaction:
                self.db.execute("ROLLBACK")
            raise
        self._events.clear()
        self._last_flush = time.monotonic()

    def action(self, identity):
        row = self.db.execute("SELECT * FROM actions WHERE id=?", (identity,)).fetchone()
        return dict(row) if row else None

    def start_action(self, action):
        self.flush_events()
        self.db.execute(
            "INSERT INTO actions VALUES(?,?,'running',NULL,?)",
            (action.id, action.model_dump_json(), time.time()),
        )

    def finish_action(self, identity, status, result):
        self.flush_events()
        self.db.execute(
            "UPDATE actions SET status=?,result=?,updated=? WHERE id=?",
            (status, json.dumps(result), time.time(), identity),
        )

    def uncertain(self):
        return [
            dict(r) for r in self.db.execute("SELECT * FROM actions WHERE status IN ('running','uncertain')")
        ]

    def record_artifact(self, path):
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with self.transaction() as db:
            row = db.execute(
                "SELECT version,sha256 FROM artifact_versions WHERE path=? ORDER BY version DESC LIMIT 1",
                (path,),
            ).fetchone()
            if row and row["sha256"] == digest:
                return {"path": path, "version": row["version"], "sha256": digest}
            version = row["version"] + 1 if row else 1
            db.execute("INSERT INTO artifact_versions VALUES(?,?,?,?)", (path, version, digest, time.time()))
        return {"path": path, "version": version, "sha256": digest}

    def artifacts(self):
        return [
            dict(r)
            for r in self.db.execute("""SELECT a.* FROM artifact_versions a JOIN
            (SELECT path,MAX(version) version FROM artifact_versions GROUP BY path) b
            ON a.path=b.path AND a.version=b.version""")
        ]

    def close(self):
        self.flush_events()
        self.db.close()
