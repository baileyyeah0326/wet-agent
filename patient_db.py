"""
Patient Database — supports PostgreSQL (cloud) and SQLite (local).

Automatically selects backend:
  - DATABASE_URL set → PostgreSQL (data persists forever)
  - Otherwise → SQLite (local file)
"""

import json
import os
from datetime import datetime

# ── Select database backend ──
DATABASE_URL = None
try:
    import streamlit as _st
    DATABASE_URL = _st.secrets.get("DATABASE_URL")
except Exception:
    pass

if not DATABASE_URL:
    DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    import psycopg2
    DB_BACKEND = "postgres"
else:
    import sqlite3
    DB_BACKEND = "sqlite"


class PatientDB:

    def __init__(self, db_path: str = "wet_patients.db"):
        self.db_path = db_path
        if DB_BACKEND == "postgres":
            self._connect_postgres()
            self._p = "%s"
        else:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._p = "?"
        self._init_tables()

    def _connect_postgres(self):
        self.conn = psycopg2.connect(DATABASE_URL)
        self.conn.autocommit = True

    def _ensure_conn(self):
        if DB_BACKEND != "postgres":
            return
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        except Exception:
            self._connect_postgres()

    def _q(self, sql):
        if DB_BACKEND == "postgres":
            return sql.replace("?", "%s")
        return sql

    def _fetchone(self, cur):
        if DB_BACKEND == "postgres":
            if cur.description is None:
                return None
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None
        else:
            row = cur.fetchone()
            return dict(row) if row else None

    def _fetchall(self, cur):
        if DB_BACKEND == "postgres":
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        else:
            return [dict(row) for row in cur.fetchall()]

    def _init_tables(self):
        self._ensure_conn()
        cur = self.conn.cursor()
        if DB_BACKEND == "postgres":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    index_trauma TEXT DEFAULT '',
                    trauma_described INTEGER DEFAULT 0,
                    trauma_bookends TEXT DEFAULT '{}',
                    therapy_goals TEXT DEFAULT '[]',
                    reason_for_therapy TEXT DEFAULT '',
                    modality TEXT DEFAULT '',
                    current_session INTEGER DEFAULT 0,
                    treatment_complete INTEGER DEFAULT 0
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_data (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    session_num INTEGER NOT NULL,
                    completed_at TEXT,
                    pcl5_score INTEGER,
                    phq9_score INTEGER,
                    suds_pre INTEGER,
                    suds_post INTEGER,
                    narrative TEXT,
                    narrative_feedback TEXT DEFAULT '{}',
                    session_summary TEXT DEFAULT ''
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clinical_observations (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    session_num INTEGER NOT NULL,
                    obs_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS avoidance_patterns (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    session_num INTEGER NOT NULL,
                    pattern TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""")
        else:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    index_trauma TEXT DEFAULT '', trauma_described INTEGER DEFAULT 0,
                    trauma_bookends TEXT DEFAULT '{}', therapy_goals TEXT DEFAULT '[]',
                    reason_for_therapy TEXT DEFAULT '', modality TEXT DEFAULT '',
                    current_session INTEGER DEFAULT 0, treatment_complete INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS session_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
                    session_num INTEGER NOT NULL, completed_at TEXT,
                    pcl5_score INTEGER, phq9_score INTEGER,
                    suds_pre INTEGER, suds_post INTEGER, narrative TEXT,
                    narrative_feedback TEXT DEFAULT '{}', session_summary TEXT DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS clinical_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
                    session_num INTEGER NOT NULL, obs_type TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS avoidance_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id TEXT NOT NULL,
                    session_num INTEGER NOT NULL, pattern TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            self.conn.commit()

    def create_patient(self, patient_id):
        self._ensure_conn()
        now = datetime.now().isoformat()
        try:
            cur = self.conn.cursor()
            cur.execute(self._q("INSERT INTO patients (patient_id, created_at) VALUES (?, ?)"),
                (patient_id, now))
            if DB_BACKEND != "postgres":
                self.conn.commit()
        except Exception:
            if DB_BACKEND == "postgres":
                self.conn.rollback()
        return self.get_patient(patient_id)

    def get_patient(self, patient_id):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q("SELECT * FROM patients WHERE patient_id = ?"), (patient_id,))
        p = self._fetchone(cur)
        if not p:
            return None
        p["trauma_bookends"] = json.loads(p["trauma_bookends"])
        p["therapy_goals"] = json.loads(p["therapy_goals"])
        p["trauma_described"] = bool(p["trauma_described"])
        p["treatment_complete"] = bool(p["treatment_complete"])
        return p

    def update_patient(self, patient_id, **kwargs):
        self._ensure_conn()
        allowed = {"index_trauma", "trauma_described", "trauma_bookends",
                    "therapy_goals", "reason_for_therapy", "modality",
                    "current_session", "treatment_complete"}
        updates = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "trauma_bookends":
                updates[k] = json.dumps(v) if isinstance(v, dict) else v
            elif k == "therapy_goals":
                updates[k] = json.dumps(v) if isinstance(v, list) else v
            elif k in ("trauma_described", "treatment_complete"):
                updates[k] = 1 if v else 0
            else:
                updates[k] = v
        if not updates:
            return
        set_clause = ", ".join(f"{k} = {self._p}" for k in updates)
        values = list(updates.values()) + [patient_id]
        cur = self.conn.cursor()
        cur.execute(f"UPDATE patients SET {set_clause} WHERE patient_id = {self._p}", values)
        if DB_BACKEND != "postgres":
            self.conn.commit()

    def save_session(self, patient_id, session_num, pcl5_score=None,
                     phq9_score=None, suds_pre=None, suds_post=None,
                     narrative=None, narrative_feedback=None, session_summary=""):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q("""
            INSERT INTO session_data
            (patient_id, session_num, completed_at, pcl5_score, phq9_score,
             suds_pre, suds_post, narrative, narrative_feedback, session_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """), (patient_id, session_num, datetime.now().isoformat(),
            pcl5_score, phq9_score, suds_pre, suds_post, narrative,
            json.dumps(narrative_feedback) if narrative_feedback else "{}",
            session_summary))
        if DB_BACKEND != "postgres":
            self.conn.commit()

    def get_sessions(self, patient_id):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q("SELECT * FROM session_data WHERE patient_id = ? ORDER BY session_num"),
            (patient_id,))
        result = self._fetchall(cur)
        for d in result:
            d["narrative_feedback"] = json.loads(d["narrative_feedback"])
        return result

    def get_score_trajectory(self, patient_id):
        sessions = self.get_sessions(patient_id)
        return {
            "pcl5": [s["pcl5_score"] for s in sessions if s["pcl5_score"] is not None],
            "phq9": [s["phq9_score"] for s in sessions if s["phq9_score"] is not None],
            "suds_pre": [s["suds_pre"] for s in sessions if s["suds_pre"] is not None],
            "suds_post": [s["suds_post"] for s in sessions if s["suds_post"] is not None],
        }

    def add_observation(self, patient_id, session_num, obs_type, content):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q("""
            INSERT INTO clinical_observations
            (patient_id, session_num, obs_type, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """), (patient_id, session_num, obs_type, content, datetime.now().isoformat()))
        if DB_BACKEND != "postgres":
            self.conn.commit()

    def get_observations(self, patient_id, session_num=None):
        self._ensure_conn()
        cur = self.conn.cursor()
        if session_num is not None:
            cur.execute(self._q(
                "SELECT * FROM clinical_observations WHERE patient_id = ? AND session_num = ? ORDER BY id"),
                (patient_id, session_num))
        else:
            cur.execute(self._q(
                "SELECT * FROM clinical_observations WHERE patient_id = ? ORDER BY id"),
                (patient_id,))
        return self._fetchall(cur)

    def add_avoidance_pattern(self, patient_id, session_num, pattern):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q("""
            INSERT INTO avoidance_patterns
            (patient_id, session_num, pattern, created_at)
            VALUES (?, ?, ?, ?)
        """), (patient_id, session_num, pattern, datetime.now().isoformat()))
        if DB_BACKEND != "postgres":
            self.conn.commit()

    def get_avoidance_patterns(self, patient_id):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q("SELECT * FROM avoidance_patterns WHERE patient_id = ? ORDER BY id"),
            (patient_id,))
        return self._fetchall(cur)

    def get_session_summaries(self, patient_id):
        self._ensure_conn()
        cur = self.conn.cursor()
        cur.execute(self._q(
            "SELECT session_num, session_summary FROM session_data "
            "WHERE patient_id = ? AND session_summary != '' ORDER BY session_num"),
            (patient_id,))
        rows = self._fetchall(cur)
        return [{"session": r["session_num"], "summary": r["session_summary"]} for r in rows]

    def build_session_context(self, patient_id):
        patient = self.get_patient(patient_id)
        if not patient:
            return "New patient. No history."
        parts = [f"Patient ID: {patient_id}", f"Current session: {patient['current_session']}"]
        if patient["reason_for_therapy"]:
            parts.append(f"Reason: {patient['reason_for_therapy']}")
        if patient["index_trauma"]:
            parts.append(f"Index trauma: {patient['index_trauma']}")
        if patient["therapy_goals"]:
            parts.append(f"Goals: {', '.join(patient['therapy_goals'])}")
        if patient["trauma_bookends"]:
            parts.append(f"Bookends: {patient['trauma_bookends']}")
        patterns = self.get_avoidance_patterns(patient_id)
        if patterns:
            parts.append(f"Avoidance patterns: {[p['pattern'] for p in patterns]}")
        summaries = self.get_session_summaries(patient_id)
        for s in summaries:
            parts.append(f"\n--- Session {s['session']} Summary ---\n{s['summary']}")
        return "\n".join(parts)

    def sync_from_state(self, patient_id, state):
        session_num = state.get("current_session", 0)
        self.update_patient(patient_id,
            index_trauma=state.get("index_trauma", ""),
            trauma_described=state.get("trauma_described", False),
            trauma_bookends=state.get("trauma_bookends", {}),
            therapy_goals=state.get("therapy_goals", []),
            reason_for_therapy=state.get("reason_for_therapy", ""),
            current_session=session_num + 1)
        summaries = state.get("session_summaries", [])
        summary_text = summaries[-1].get("summary", "") if summaries else ""
        self.save_session(patient_id, session_num, session_summary=summary_text)
        for obs in state.get("clinical_observations", []):
            self.add_observation(patient_id, session_num, obs.get("type", ""), obs.get("content", ""))
        for ap in state.get("avoidance_patterns", []):
            self.add_avoidance_pattern(patient_id, ap.get("session", session_num), ap.get("pattern", ""))

    def close(self):
        self.conn.close()

    def print_patient_summary(self, patient_id):
        p = self.get_patient(patient_id)
        if not p:
            print(f"  Patient {patient_id} not found in database.")
            return
        print(f"  ┌─── DB: Patient {patient_id} ──────────────────────")
        print(f"  │ created:           {p['created_at']}")
        print(f"  │ current_session:   {p['current_session']}")
        print(f"  │ reason_for_therapy: {p['reason_for_therapy'] or '—'}")
        print(f"  │ trauma_described:  {p['trauma_described']}")
        print(f"  │ index_trauma:      {p['index_trauma'] or '—'}")
        print(f"  │ therapy_goals:     {p['therapy_goals'] or '—'}")
        print(f"  │ trauma_bookends:   {p['trauma_bookends'] or '—'}")
        patterns = self.get_avoidance_patterns(patient_id)
        print(f"  │ avoidance_patterns: {[ap['pattern'] for ap in patterns] if patterns else '—'}")
        traj = self.get_score_trajectory(patient_id)
        print(f"  │ pcl5_scores:      {traj['pcl5'] or '—'}")
        summaries = self.get_session_summaries(patient_id)
        if summaries:
            print(f"  │ session_summaries: {len(summaries)}")
            for s in summaries:
                print(f"  │   S{s['session']}: {s['summary'][:80]}...")
        else:
            print(f"  │ session_summaries: —")
        obs = self.get_observations(patient_id)
        print(f"  │ observations:      {len(obs)}")
        for o in obs:
            print(f"  │   [{o['obs_type']}] {o['content']}")
        print(f"  └────────────────────────────────────────────")