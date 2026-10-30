import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from .models import PHASES
from .rules import VERSION


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY, input TEXT NOT NULL, input_hash TEXT NOT NULL,
              configuration TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
              contract_version TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT,
              lease_owner TEXT, lease_until REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS outputs (
              run_id TEXT NOT NULL, phase TEXT NOT NULL, value TEXT NOT NULL,
              created_at TEXT NOT NULL, PRIMARY KEY(run_id,phase));
            CREATE TABLE IF NOT EXISTS calls (
              run_id TEXT NOT NULL, call_key TEXT NOT NULL, value TEXT NOT NULL,
              created_at TEXT NOT NULL, PRIMARY KEY(run_id,call_key));
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              phase TEXT NOT NULL, worker TEXT NOT NULL, status TEXT NOT NULL,
              message TEXT NOT NULL, created_at TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def create(self, request, provider, model):
        rid = str(uuid.uuid4())
        config = request.configuration.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(
                {"input": request.input, "configuration": config}, sort_keys=True
            ).encode()
        ).hexdigest()
        with self.connect() as c:
            c.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    request.input,
                    digest,
                    json.dumps(config),
                    provider,
                    model,
                    VERSION,
                    "QUEUED",
                    PHASES[0],
                    now(),
                    now(),
                    None,
                    None,
                    0,
                ),
            )
        return rid

    def get(self, rid):
        with self.connect() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["configuration"] = json.loads(d["configuration"])
            d.pop("lease_owner")
            d.pop("lease_until")
            rows = {
                r["phase"]: json.loads(r["value"])
                for r in c.execute("SELECT * FROM outputs WHERE run_id=?", (rid,))
            }
            d["outputs"] = {p: rows[p] for p in PHASES if p in rows}
            validation = c.execute(
                "SELECT value FROM calls WHERE run_id=? AND call_key=?",
                (rid, "validation-results"),
            ).fetchone()
            d["validation_results"] = (
                json.loads(validation["value"]) if validation else None
            )
            d["events"] = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM events WHERE run_id=? ORDER BY id DESC LIMIT 250",
                    (rid,),
                )
            ][::-1]
            return d

    def history(self):
        with self.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT id,input,status,phase,created_at,provider,model FROM runs ORDER BY created_at DESC LIMIT 50"
                )
            ]

    def claim(self, owner, provider, model):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute(
                "SELECT id FROM runs WHERE provider=? AND model=? AND (status='QUEUED' OR (status='RUNNING' AND lease_until<?)) ORDER BY created_at LIMIT 1",
                (provider, model, time.time()),
            ).fetchone()
            if not r:
                return None
            c.execute(
                "UPDATE runs SET status='RUNNING',lease_owner=?,lease_until=?,updated_at=? WHERE id=?",
                (owner, time.time() + 60, now(), r["id"]),
            )
            return r["id"]

    def heartbeat(self, rid, owner):
        with self.connect() as c:
            result = c.execute(
                "UPDATE runs SET lease_until=? WHERE id=? AND lease_owner=? AND status='RUNNING'",
                (time.time() + 60, rid, owner),
            )
            return result.rowcount == 1

    def commit_phase(self, rid, phase, value, owner):
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            r = c.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
            if r["lease_owner"] != owner or r["lease_until"] < time.time():
                raise RuntimeError("Execution lease lost")
            current = PHASES.index(r["phase"])
            target = PHASES.index(phase)
            if target != current + 1:
                raise ValueError("Invalid phase ordering")
            c.execute(
                "INSERT INTO outputs VALUES (?,?,?,?)",
                (rid, phase, json.dumps(value), now()),
            )
            c.execute(
                "UPDATE runs SET phase=?,updated_at=?,status=? WHERE id=?",
                (phase, now(), "COMPLETED" if phase == PHASES[-1] else "RUNNING", rid),
            )

    def cache(self, rid, key, value=None):
        with self.connect() as c:
            if value is not None:
                c.execute(
                    "INSERT OR IGNORE INTO calls VALUES (?,?,?,?)",
                    (rid, key, json.dumps(value), now()),
                )
            row = c.execute(
                "SELECT value FROM calls WHERE run_id=? AND call_key=?", (rid, key)
            ).fetchone()
            return json.loads(row["value"]) if row else None

    def event(self, rid, phase, worker, status, message):
        with self.connect() as c:
            c.execute(
                "INSERT INTO events(run_id,phase,worker,status,message,created_at) VALUES (?,?,?,?,?,?)",
                (rid, phase, worker, status, message, now()),
            )

    def fail(self, rid, owner, error):
        with self.connect() as c:
            c.execute(
                "UPDATE runs SET status='FAILED',error=?,updated_at=?,lease_owner=NULL,lease_until=0 WHERE id=? AND lease_owner=?",
                (error, now(), rid, owner),
            )

    def retry(self, rid):
        with self.connect() as c:
            return (
                c.execute(
                    "UPDATE runs SET status='QUEUED',error=NULL,lease_owner=NULL,lease_until=0,updated_at=? WHERE id=? AND status='FAILED'",
                    (now(), rid),
                ).rowcount
                == 1
            )
