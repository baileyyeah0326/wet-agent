"""
Patient Database — SQLite persistent storage for clinical data.

Stores patient profiles and session data independently of LangGraph's
checkpointer. This means:
- LangGraph SqliteSaver handles conversation state (messages, step position)
- PatientDB handles clinical data (scores, trauma, goals, summaries)

The two are complementary:
- Checkpointer = "where are we in the conversation right now?"
- PatientDB = "what do we know about this patient across all sessions?"
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class PatientDB:
    """SQLite database for persistent patient clinical data."""

    def __init__(self, db_path: str = "wet_patients.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """Create tables if they don't exist."""
        self.conn.executescript("""
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
            );

            CREATE TABLE IF NOT EXISTS session_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                session_num INTEGER NOT NULL,
                completed_at TEXT,
                pcl5_score INTEGER,
                phq9_score INTEGER,
                suds_pre INTEGER,
                suds_post INTEGER,
                narrative TEXT,
                narrative_feedback TEXT DEFAULT '{}',
                session_summary TEXT DEFAULT '',
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            );

            CREATE TABLE IF NOT EXISTS clinical_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                session_num INTEGER NOT NULL,
                obs_type TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            );

            CREATE TABLE IF NOT EXISTS avoidance_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                session_num INTEGER NOT NULL,
                pattern TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            );
        """)
        self.conn.commit()

    # ── Patient CRUD ──────────────────────────────────────────────

    def create_patient(self, patient_id: str) -> dict:
        """Create a new patient record. Returns patient dict."""
        now = datetime.now().isoformat()
        try:
            self.conn.execute(
                "INSERT INTO patients (patient_id, created_at) VALUES (?, ?)",
                (patient_id, now))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # patient already exists
        return self.get_patient(patient_id)

    def get_patient(self, patient_id: str) -> dict | None:
        """Get patient profile."""
        row = self.conn.execute(
            "SELECT * FROM patients WHERE patient_id = ?",
            (patient_id,)).fetchone()
        if not row:
            return None
        p = dict(row)
        p["trauma_bookends"] = json.loads(p["trauma_bookends"])
        p["therapy_goals"] = json.loads(p["therapy_goals"])
        p["trauma_described"] = bool(p["trauma_described"])
        p["treatment_complete"] = bool(p["treatment_complete"])
        return p

    def update_patient(self, patient_id: str, **kwargs):
        """Update patient profile fields."""
        allowed = {
            "index_trauma", "trauma_described", "trauma_bookends",
            "therapy_goals", "reason_for_therapy", "modality",
            "current_session", "treatment_complete",
        }
        updates = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            if k == "trauma_bookends":
                updates[k] = json.dumps(v) if isinstance(v, dict) else v
            elif k == "therapy_goals":
                updates[k] = json.dumps(v) if isinstance(v, list) else v
            elif k == "trauma_described" or k == "treatment_complete":
                updates[k] = 1 if v else 0
            else:
                updates[k] = v

        if not updates:
            return

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [patient_id]
        self.conn.execute(
            f"UPDATE patients SET {set_clause} WHERE patient_id = ?",
            values)
        self.conn.commit()

    # ── Session Data ──────────────────────────────────────────────

    def save_session(self, patient_id: str, session_num: int,
                     pcl5_score: int = None, phq9_score: int = None,
                     suds_pre: int = None, suds_post: int = None,
                     narrative: str = None,
                     narrative_feedback: dict = None,
                     session_summary: str = ""):
        """Save session data after a session completes."""
        self.conn.execute("""
            INSERT INTO session_data
            (patient_id, session_num, completed_at, pcl5_score, phq9_score,
             suds_pre, suds_post, narrative, narrative_feedback, session_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id, session_num, datetime.now().isoformat(),
            pcl5_score, phq9_score, suds_pre, suds_post,
            narrative,
            json.dumps(narrative_feedback) if narrative_feedback else "{}",
            session_summary,
        ))
        self.conn.commit()

    def get_sessions(self, patient_id: str) -> list[dict]:
        """Get all session data for a patient, ordered by session number."""
        rows = self.conn.execute(
            "SELECT * FROM session_data WHERE patient_id = ? ORDER BY session_num",
            (patient_id,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["narrative_feedback"] = json.loads(d["narrative_feedback"])
            result.append(d)
        return result

    def get_score_trajectory(self, patient_id: str) -> dict:
        """Get PCL-5 and PHQ-9 score trajectories."""
        sessions = self.get_sessions(patient_id)
        return {
            "pcl5": [s["pcl5_score"] for s in sessions if s["pcl5_score"] is not None],
            "phq9": [s["phq9_score"] for s in sessions if s["phq9_score"] is not None],
            "suds_pre": [s["suds_pre"] for s in sessions if s["suds_pre"] is not None],
            "suds_post": [s["suds_post"] for s in sessions if s["suds_post"] is not None],
        }

    # ── Clinical Observations ─────────────────────────────────────

    def add_observation(self, patient_id: str, session_num: int,
                        obs_type: str, content: str):
        """Add a clinical observation."""
        self.conn.execute("""
            INSERT INTO clinical_observations
            (patient_id, session_num, obs_type, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_id, session_num, obs_type, content,
              datetime.now().isoformat()))
        self.conn.commit()

    def get_observations(self, patient_id: str,
                         session_num: int = None) -> list[dict]:
        """Get clinical observations. Optionally filter by session."""
        if session_num is not None:
            rows = self.conn.execute(
                "SELECT * FROM clinical_observations "
                "WHERE patient_id = ? AND session_num = ? ORDER BY id",
                (patient_id, session_num)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM clinical_observations "
                "WHERE patient_id = ? ORDER BY id",
                (patient_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Avoidance Patterns ────────────────────────────────────────

    def add_avoidance_pattern(self, patient_id: str, session_num: int,
                              pattern: str):
        """Add an avoidance pattern."""
        self.conn.execute("""
            INSERT INTO avoidance_patterns
            (patient_id, session_num, pattern, created_at)
            VALUES (?, ?, ?, ?)
        """, (patient_id, session_num, pattern,
              datetime.now().isoformat()))
        self.conn.commit()

    def get_avoidance_patterns(self, patient_id: str) -> list[dict]:
        """Get all avoidance patterns across sessions."""
        rows = self.conn.execute(
            "SELECT * FROM avoidance_patterns WHERE patient_id = ? ORDER BY id",
            (patient_id,)).fetchall()
        return [dict(r) for r in rows]

    # ── Session Summaries ─────────────────────────────────────────

    def get_session_summaries(self, patient_id: str) -> list[str]:
        """Get all session summaries for building context."""
        rows = self.conn.execute(
            "SELECT session_num, session_summary FROM session_data "
            "WHERE patient_id = ? AND session_summary != '' "
            "ORDER BY session_num",
            (patient_id,)).fetchall()
        return [{"session": r["session_num"], "summary": r["session_summary"]}
                for r in rows]

    # ── Build Context for LLM ─────────────────────────────────────

    def build_session_context(self, patient_id: str) -> str:
        """Build a context string from patient history for LLM system prompt.
        
        Used at the start of each new session to give the agent
        continuity without replaying old conversations.
        """
        patient = self.get_patient(patient_id)
        if not patient:
            return "New patient. No history."

        parts = []
        parts.append(f"Patient ID: {patient_id}")
        parts.append(f"Current session: {patient['current_session']}")

        if patient["reason_for_therapy"]:
            parts.append(f"Reason: {patient['reason_for_therapy']}")
        if patient["index_trauma"]:
            parts.append(f"Index trauma: {patient['index_trauma']}")
        if patient["therapy_goals"]:
            parts.append(f"Goals: {', '.join(patient['therapy_goals'])}")
        if patient["trauma_bookends"]:
            parts.append(f"Bookends: {patient['trauma_bookends']}")

        # Score trajectory
        traj = self.get_score_trajectory(patient_id)
        if traj["pcl5"]:
            parts.append(f"PCL-5 trajectory: {traj['pcl5']}")
        if traj["phq9"]:
            parts.append(f"PHQ-9 trajectory: {traj['phq9']}")

        # Avoidance patterns
        patterns = self.get_avoidance_patterns(patient_id)
        if patterns:
            p_list = [p["pattern"] for p in patterns]
            parts.append(f"Avoidance patterns: {p_list}")

        # Session summaries
        summaries = self.get_session_summaries(patient_id)
        for s in summaries:
            parts.append(f"\n--- Session {s['session']} Summary ---\n{s['summary']}")

        return "\n".join(parts)

    # ── Sync from WETState (called after session completes) ───────

    def sync_from_state(self, patient_id: str, state: dict):
        """Sync WETState data to database after session completes.
        
        Called after step13_closing. Writes all extracted data to DB.
        """
        session_num = state.get("current_session", 0)

        # Update patient profile
        self.update_patient(patient_id,
            index_trauma=state.get("index_trauma", ""),
            trauma_described=state.get("trauma_described", False),
            trauma_bookends=state.get("trauma_bookends", {}),
            therapy_goals=state.get("therapy_goals", []),
            reason_for_therapy=state.get("reason_for_therapy", ""),
            current_session=session_num + 1,  # ready for next session
        )

        # Save session data
        summaries = state.get("session_summaries", [])
        summary_text = ""
        if summaries:
            latest = summaries[-1]
            summary_text = latest.get("summary", "")

        self.save_session(
            patient_id=patient_id,
            session_num=session_num,
            session_summary=summary_text,
        )

        # Save observations
        for obs in state.get("clinical_observations", []):
            self.add_observation(
                patient_id=patient_id,
                session_num=session_num,
                obs_type=obs.get("type", ""),
                content=obs.get("content", ""),
            )

        # Save avoidance patterns
        for ap in state.get("avoidance_patterns", []):
            self.add_avoidance_pattern(
                patient_id=patient_id,
                session_num=ap.get("session", session_num),
                pattern=ap.get("pattern", ""),
            )

    # ── Utility ───────────────────────────────────────────────────

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def print_patient_summary(self, patient_id: str):
        """Print a human-readable patient summary matching _print_state format."""
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

        # Avoidance patterns
        patterns = self.get_avoidance_patterns(patient_id)
        if patterns:
            print(f"  │ avoidance_patterns: {[ap['pattern'] for ap in patterns]}")
        else:
            print(f"  │ avoidance_patterns: —")

        # Score trajectory
        traj = self.get_score_trajectory(patient_id)
        print(f"  │ pcl5_scores:      {traj['pcl5'] or '—'}")
        print(f"  │ phq9_scores:      {traj['phq9'] or '—'}")
        print(f"  │ suds_pre:         {traj['suds_pre'] or '—'}")
        print(f"  │ suds_post:        {traj['suds_post'] or '—'}")

        # Session summaries
        summaries = self.get_session_summaries(patient_id)
        if summaries:
            print(f"  │ session_summaries: {len(summaries)}")
            for s in summaries:
                print(f"  │   S{s['session']}: {s['summary']}...")
        else:
            print(f"  │ session_summaries: —")

        # Observations (show all with type)
        obs = self.get_observations(patient_id)
        print(f"  │ observations:      {len(obs)}")
        for o in obs:
            print(f"  │   [{o['obs_type']}] {o['content']}")

        # Session data
        sessions = self.get_sessions(patient_id)
        if sessions:
            print(f"  │ sessions:         {len(sessions)}")
            for s in sessions:
                print(f"  │   S{s['session_num']}: "
                      f"pcl5={s['pcl5_score']}, phq9={s['phq9_score']}, "
                      f"suds={s['suds_pre']}→{s['suds_post']}")
        else:
            print(f"  │ sessions:         —")

        print(f"  └────────────────────────────────────────────")