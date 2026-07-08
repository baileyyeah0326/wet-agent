"""
WET Agent — Session 1 (Writing Session)

Same architecture as Session 0: skill-file driven, prompt + judge pattern.
Imports shared utilities from session0.py.

Key differences from Session 0:
  - Cross-session context (reads Session 0 data)
  - SUDs collection (numeric 0-100)
  - 30-minute writing task (narrative collection)
  - Briefer discussions (process-focused, not exploratory)
"""

from pathlib import Path
import json
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

# Import shared components from session0
from session0 import (
    WETState, STEP_LABELS as S0_LABELS,
    _llm, _llm_json, _ctx, _get_last_human, _get_follow_up,
    _add_obs, _ai_msg, _safe_json, _safety_screen,
    _make_safety_prompt, _make_safety_judge, _safety_result_node,
    _safety_q1_router, _safety_q2_router, _safety_q3_router,
    _safety_q4_router, _safety_q5_router, _safety_q6_router,
    _safety_q6_recency_router, _classify_risk,
    _build_json_schema, _parse_extract_spec,
    _db, PatientDB, SAFETY_QS,
)
import session0

import re

# ═══════════════════════════════════════════════════════════════════
# Session 1 Skill Loader
# ═══════════════════════════════════════════════════════════════════

SKILLS_DIR_S1 = Path(__file__).parent / "skills" / "session1"


def _load_skill_s1(filename):
    path = SKILLS_DIR_S1 / filename
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")
    text = path.read_text(encoding="utf-8")
    sections = {}
    current_key = None
    current_lines = []
    for line in text.split("\n"):
        m = re.match(r'^## (.+)', line)
        if m:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1).strip().lower().replace(" ", "_").replace("-", "_")
            current_lines = []
        elif current_key:
            current_lines.append(line)
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


SKILLS_S1 = {
    "s1_step1":  _load_skill_s1("step01_welcome.md"),
    "s1_step3":  _load_skill_s1("step03_procedure_review.md"),
    "s1_step4":  _load_skill_s1("step04_bookends_review.md"),
    "s1_step5":  _load_skill_s1("step05_writing_instructions.md"),
    "s1_step6":  _load_skill_s1("step06_questions.md"),
    "s1_step7":  _load_skill_s1("step07_suds_intro.md"),
    "s1_step8":  _load_skill_s1("step08_writing_task.md"),
    "s1_step9":  _load_skill_s1("step09_suds_post.md"),
    "s1_step10": _load_skill_s1("step10_writing_discussion.md"),
    "s1_step11": _load_skill_s1("step11_closing.md"),
}


# ═══════════════════════════════════════════════════════════════════
# Step Labels
# ═══════════════════════════════════════════════════════════════════

STEP_LABELS_S1 = {
    "s1_step1":  "Step 1/11  — Welcome back",
    "s1_step3":  "Step 3/11  — General writing directions",
    "s1_step4":  "Step 4/11  — Bookends review",
    "s1_step5":  "Step 5/11  — Writing instructions",
    "s1_step6":  "Step 6/11  — Questions before starting",
    "s1_step7":  "Step 7/11  — SUDs introduction + pre-writing",
    "s1_step8":  "Step 8/11  — Writing task",
    "s1_step9":  "Step 9/11  — Post-writing SUDs",
    "s1_step10": "Step 10/11 — Writing discussion",
    "s1_step11": "Step 11/11 — Closing",
}


# ═══════════════════════════════════════════════════════════════════
# Session 1 make_prompt / make_judge
# ═══════════════════════════════════════════════════════════════════

def make_prompt_s1(step_name):
    def prompt_fn(state):
        if state.get("current_step") != step_name:
            skill = SKILLS_S1[step_name]
            task = f"[TASK] {skill.get('prompt_task', 'Continue.')}"
            notes = skill.get("clinical_notes", "")
            if notes:
                task += f"\n\nCLINICAL NOTES:\n{notes}"
            task += ("\n\nCROSS-STEP AWARENESS: Review the full conversation "
                     "history. Reference what the patient already shared. "
                     "Do NOT repeat questions already answered.")

            # Inject Session 0 context for cross-session continuity
            if state.get("session_summaries"):
                s0_summary = state["session_summaries"][-1].get("summary", "")
                task += f"\n\nSESSION 0 SUMMARY:\n{s0_summary}"
            if state.get("trauma_bookends"):
                task += f"\n\nBOOKENDS FROM SESSION 0: {state['trauma_bookends']}"

            content = _llm(state, task)
            label = STEP_LABELS_S1.get(step_name, step_name)
            return {"current_step": step_name, "awaiting_input": True,
                    "messages": [_ai_msg(content, label)]}
        return {"current_step": step_name, "messages": []}
    return prompt_fn


def make_judge_s1(step_name):
    spec = _parse_extract_spec_s1(step_name)

    def judge_fn(state):
        # Safety screen
        screen = _safety_screen(state)
        if screen["current_step"] == "safety_q1":
            return {"current_step": "safety_q1",
                    "safety_return_step": step_name,
                    "messages": []}

        # Normal judge
        skill = SKILLS_S1[step_name]
        criteria = skill.get("judge_criteria", "pass=true if patient responded.")
        follow_guidance = skill.get("follow_up_guidance", "")
        json_schema = _build_json_schema(spec)

        task = (f"[TASK] Evaluate patient response for {step_name}.\n\n"
                f"Review ALL messages in this step.\n\n"
                f"CRITERIA:\n{criteria}\n\n"
                "ANTI-LOOPING RULE: If the core criteria are met, "
                "set pass=true. Do NOT keep looping.\n\n")
        if follow_guidance:
            task += (
                f"FOLLOW-UP GUIDANCE (if pass=false):\n{follow_guidance}\n\n"
                "The follow_up must be NATURAL and end with an open "
                "question or invitation.\n\n")
        task += f"JSON only:\n{json_schema}"

        default = {"pass": False, "follow_up": None}
        for f in spec["fields"]:
            default[f["name"]] = [] if f["type"] == "list" else None

        result = _llm_json(state, task, default)

        if not result.get("pass", True):
            fu = _get_follow_up(state, result,
                f"[TASK] Respond for {step_name}. Guide. 2-3 sentences.")
            label = STEP_LABELS_S1.get(step_name, step_name)
            return {"current_step": step_name,
                    "messages": [_ai_msg(fu, label)]}

        # PASS — extract data
        updates = {"current_step": f"{step_name}_done", "messages": []}

        for f in spec["fields"]:
            val = result.get(f["name"])
            if val is not None:
                updates[f["name"]] = val

        # Special: SUDs — convert to int and store in list
        if step_name == "s1_step7" and result.get("suds_pre"):
            try:
                suds_val = int(result["suds_pre"])
                updates["suds_pre"] = state.get("suds_pre", []) + [suds_val]
            except (ValueError, TypeError):
                pass

        if step_name == "s1_step9" and result.get("suds_post"):
            try:
                suds_val = int(result["suds_post"])
                updates["suds_post"] = state.get("suds_post", []) + [suds_val]
            except (ValueError, TypeError):
                pass

        # Special: narrative — store in narratives list
        if step_name == "s1_step8" and result.get("narrative"):
            updates["narratives"] = state.get("narratives", []) + [result["narrative"]]

        # Special: bookends update from step4
        if step_name == "s1_step4":
            if result.get("beginning") and result.get("end"):
                updates["trauma_bookends"] = {
                    "beginning": result.get("beginning", ""),
                    "end": result.get("end", ""),
                }

        # Observation
        if spec["observation"]:
            obs = result.get("observation_summary", "")
            if not obs:
                obs = _get_last_human(state)[:200]
            updates["clinical_observations"] = _add_obs(
                state, spec["observation"], obs)

        # DB write
        db = session0._db
        if db is not None:
            pid = state.get("patient_id", "")
            session_num = state.get("current_session", 0)

            db_updates = {k: v for k, v in updates.items()
                          if k in ("trauma_bookends",)}
            if db_updates:
                db.update_patient(pid, **db_updates)

            if spec["observation"]:
                db.add_observation(pid, session_num,
                    spec["observation"],
                    obs if isinstance(obs, str) else json.dumps(obs))

        return updates
    return judge_fn


def _parse_extract_spec_s1(step_name):
    raw = SKILLS_S1[step_name].get("data_to_extract", "")
    if not raw or raw.strip().lower() == "none":
        return {"fields": [], "observation": None}

    fields = []
    observation = None
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("observation:"):
            observation = line.split(":", 1)[1].strip()
        elif line.startswith("field:"):
            parts = [p.strip() for p in line.split("|")]
            field = {"name": "", "type": "string", "description": "",
                     "nullable": False, "values": []}
            for p in parts:
                k, _, v = p.partition(":")
                k = k.strip()
                v = v.strip()
                if k == "field": field["name"] = v
                elif k == "type": field["type"] = v
                elif k == "description": field["description"] = v
                elif k == "nullable": field["nullable"] = v.lower() == "true"
                elif k == "values": field["values"] = [x.strip() for x in v.split(",")]
            if field["name"]:
                fields.append(field)
    return {"fields": fields, "observation": observation}


# ═══════════════════════════════════════════════════════════════════
# Step 10: closing (no judge)
# ═══════════════════════════════════════════════════════════════════

def step11_closing(state):
    skill = SKILLS_S1["s1_step11"]
    task = f"[TASK] {skill.get('prompt_task', 'Close.')}"
    notes = skill.get("clinical_notes", "")
    if notes:
        task += f"\n\nCLINICAL NOTES:\n{notes}"
    content = _llm(state, task)

    # Generate session summary
    summary = _llm_json(state, (
        "[TASK] Generate a clinical session summary for Session 1.\n\n"
        f"Patient's trauma: {state.get('index_trauma','')}\n"
        f"Pre-writing SUDs: {state.get('suds_pre', [])}\n"
        f"Post-writing SUDs: {state.get('suds_post', [])}\n"
        f"Bookends: {state.get('trauma_bookends', {})}\n\n"
        "Review the conversation and generate:\n"
        "JSON only:\n{\n"
        '  "summary": "100-word summary of Session 1: writing engagement, '
        'emotional response, SUDs change, any notable observations.",\n'
        '  "session2_priorities": ["priority1", "priority2"]\n'
        "}"
    ), {"summary": "Session 1 completed.", "session2_priorities": []})

    session_summary = {
        "session": 1,
        "summary": summary.get("summary", ""),
        "session2_priorities": summary.get("session2_priorities", []),
        "timestamp": datetime.now().isoformat(),
    }

    summary_text = summary.get("summary", "Session 1 completed.")

    updates = {
        "current_step": "s1_step11_done",
        "session_complete": True,
        "messages": [_ai_msg(content, STEP_LABELS_S1.get("s1_step11", "Closing"))],
        "session_summaries": state.get("session_summaries", []) + [session_summary],
        "clinical_observations": _add_obs(
            state, "session1_complete", summary_text),
    }

    db = session0._db
    if db is not None:
        pid = state.get("patient_id", "")
        session_num = state.get("current_session", 0)

        # Save session with SUDs and narrative
        suds_pre = state.get("suds_pre", [])
        suds_post = state.get("suds_post", [])
        narratives = state.get("narratives", [])
        db.save_session(pid, session_num,
            suds_pre=suds_pre[-1] if suds_pre else None,
            suds_post=suds_post[-1] if suds_post else None,
            narrative=narratives[-1] if narratives else None,
            session_summary=summary_text)
        db.add_observation(pid, session_num,
            "session1_complete", summary_text)
        db.update_patient(pid, current_session=session_num + 1)

    return updates


# ═══════════════════════════════════════════════════════════════════
# Graph
# ═══════════════════════════════════════════════════════════════════

def _make_judge_router_s1(step_name, next_prompt):
    def fn(state):
        cs = state["current_step"]
        if cs == "safety_q1":
            return "safety_q1_prompt"
        if cs == f"{step_name}_done":
            return next_prompt
        return f"{step_name}_prompt"
    return fn


STEP_DEFS_S1 = [
    ("s1_step1",  make_prompt_s1("s1_step1"),  make_judge_s1("s1_step1")),
    ("s1_step3",  make_prompt_s1("s1_step3"),  make_judge_s1("s1_step3")),
    ("s1_step4",  make_prompt_s1("s1_step4"),  make_judge_s1("s1_step4")),
    ("s1_step5",  make_prompt_s1("s1_step5"),  make_judge_s1("s1_step5")),
    ("s1_step6",  make_prompt_s1("s1_step6"),  make_judge_s1("s1_step6")),
    ("s1_step7",  make_prompt_s1("s1_step7"),  make_judge_s1("s1_step7")),
    ("s1_step8",  make_prompt_s1("s1_step8"),  make_judge_s1("s1_step8")),
    ("s1_step9",  make_prompt_s1("s1_step9"),  make_judge_s1("s1_step9")),
    ("s1_step10", make_prompt_s1("s1_step10"), make_judge_s1("s1_step10")),
]

SAFETY_ROUTERS_S1 = {
    "q1": _safety_q1_router,
    "q2": _safety_q2_router,
    "q3": _safety_q3_router,
    "q4": _safety_q4_router,
    "q5": _safety_q5_router,
    "q6": _safety_q6_router,
    "q6_recency": _safety_q6_recency_router,
}


def build_session1():
    g = StateGraph(WETState)

    # Main therapy nodes
    for name, pfn, jfn in STEP_DEFS_S1:
        g.add_node(f"{name}_prompt", pfn)
        g.add_node(f"{name}_judge", jfn)
    g.add_node("s1_step11_closing", step11_closing)

    # Safety subgraph nodes (reused from session0)
    for qk in SAFETY_QS:
        g.add_node(f"safety_{qk}_prompt", _make_safety_prompt(qk))
        g.add_node(f"safety_{qk}_judge", _make_safety_judge(qk))
    g.add_node("safety_result", _safety_result_node)

    # Main edges
    g.add_edge(START, "s1_step1_prompt")

    for i, (name, _, _) in enumerate(STEP_DEFS_S1):
        g.add_edge(f"{name}_prompt", f"{name}_judge")

        if i < len(STEP_DEFS_S1) - 1:
            nxt = f"{STEP_DEFS_S1[i+1][0]}_prompt"
        else:
            nxt = "s1_step11_closing"

        g.add_conditional_edges(f"{name}_judge",
            _make_judge_router_s1(name, nxt),
            {nxt: nxt,
             f"{name}_prompt": f"{name}_prompt",
             "safety_q1_prompt": "safety_q1_prompt"})

    g.add_edge("s1_step11_closing", END)

    # Safety subgraph edges (same as session0)
    for qk in SAFETY_QS:
        g.add_edge(f"safety_{qk}_prompt", f"safety_{qk}_judge")

    for qk in SAFETY_QS:
        router = SAFETY_ROUTERS_S1[qk]
        possible = set()
        if qk == "q1": possible = {"safety_q1_prompt", "safety_q2_prompt"}
        elif qk == "q2": possible = {"safety_q2_prompt", "safety_q3_prompt", "safety_q6_prompt"}
        elif qk == "q3": possible = {"safety_q3_prompt", "safety_q4_prompt"}
        elif qk == "q4": possible = {"safety_q4_prompt", "safety_q5_prompt"}
        elif qk == "q5": possible = {"safety_q5_prompt", "safety_q6_prompt"}
        elif qk == "q6": possible = {"safety_q6_prompt", "safety_q6_recency_prompt", "safety_result"}
        elif qk == "q6_recency": possible = {"safety_q6_recency_prompt", "safety_result"}

        g.add_conditional_edges(f"safety_{qk}_judge", router,
            {d: d for d in possible})

    # Safety result routing
    all_prompts = {f"{s[0]}_prompt": f"{s[0]}_prompt" for s in STEP_DEFS_S1}
    all_prompts["safety_stop"] = END

    def _safety_result_router(state):
        if state.get("current_step") == "safety_stop":
            return "safety_stop"
        return_step = state.get("safety_return_step", "s1_step1")
        return f"{return_step}_prompt"

    g.add_conditional_edges("safety_result", _safety_result_router,
        all_prompts)

    return g


# ═══════════════════════════════════════════════════════════════════
# App (Session 1)
# ═══════════════════════════════════════════════════════════════════

DB_DIR = Path(__file__).parent / "data"


def create_app_s1():
    import sqlite3
    DB_DIR.mkdir(exist_ok=True)

    conn = sqlite3.connect(str(DB_DIR / "checkpoints.db"),
                           check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    db = PatientDB(str(DB_DIR / "patients.db"))
    session0._db = db

    graph = build_session1()

    interrupt_nodes = [f"{s[0]}_prompt" for s in STEP_DEFS_S1]
    interrupt_nodes += [f"safety_{qk}_prompt" for qk in SAFETY_QS]

    app = graph.compile(checkpointer=checkpointer,
        interrupt_after=interrupt_nodes)

    return app, db


def start_session1(app, db, pid):
    """Start Session 1. Loads Session 0 data for continuity."""
    config = {"configurable": {"thread_id": f"patient_{pid}_s1"}}

    existing = app.get_state(config)
    if existing and existing.values and existing.values.get("current_step"):
        if existing.values.get("session_complete"):
            return existing.values
        return existing.values

    # Load Session 0 data for continuity
    patient = db.get_patient(pid)
    s0_summaries = db.get_session_summaries(pid)
    s0_observations = db.get_observations(pid, session_num=0)
    s0_avoidance = db.get_avoidance_patterns(pid)

    session_summaries = [{"session": s["session"], "summary": s["summary"]}
                         for s in s0_summaries]

    clinical_obs = [{"session": o["session_num"], "type": o["obs_type"],
                     "content": o["content"], "timestamp": o["created_at"]}
                    for o in s0_observations]

    avoidance = [{"session": a["session_num"], "pattern": a["pattern"],
                  "timestamp": a["created_at"]}
                 for a in s0_avoidance]

    return app.invoke({
        "current_session": 1,
        "current_step": "",
        "session_complete": False,
        "awaiting_input": False,
        "patient_id": pid,
        "index_trauma": patient.get("index_trauma", "") if patient else "",
        "trauma_described": patient.get("trauma_described", False) if patient else False,
        "trauma_bookends": patient.get("trauma_bookends", {}) if patient else {},
        "therapy_goals": patient.get("therapy_goals", []) if patient else [],
        "reason_for_therapy": patient.get("reason_for_therapy", "") if patient else "",
        "pcl5_scores": [],
        "phq9_scores": [],
        "suds_pre": [],
        "suds_post": [],
        "narratives": [],
        "narrative_feedback": [],
        "messages": [],
        "modality": "",
        "session_summaries": session_summaries,
        "clinical_observations": clinical_obs,
        "avoidance_patterns": avoidance,
        "safety_answers": {},
        "safety_risk": "",
        "safety_return_step": "",
    }, config=config)


def run_turn_s1(app, pid, message):
    config = {"configurable": {"thread_id": f"patient_{pid}_s1"}}
    app.update_state(config, {"messages": [HumanMessage(content=message)]})
    return app.invoke(None, config=config)


def get_ai_msg(result):
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage):
            return msg.content
    return ""


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  WET Agent — Session 1 (Writing Session)")
    print("=" * 60)

    app, db = create_app_s1()

    pid = input("  Enter Patient ID: ").strip()
    if not pid:
        pid = "P001"

    # Check Session 0 completed
    patient = db.get_patient(pid)
    if not patient:
        print(f"  Patient {pid} not found. Complete Session 0 first.")
        db.close()
        import sys
        sys.exit(0)

    if patient.get("current_session", 0) < 1:
        print(f"  Session 0 not complete for {pid}. Complete Session 0 first.")
        db.close()
        import sys
        sys.exit(0)

    print(f"  Starting Session 1 for {pid}\n")

    result = start_session1(app, db, pid)

    if result.get("session_complete"):
        print("  Session 1 already complete.")
        db.close()
        import sys
        sys.exit(0)

    step = result.get("current_step", "")
    label = STEP_LABELS_S1.get(step.replace("_done", ""), step)
    print(f"  [{label}]")
    print(f"\nTHERAPIST:\n{get_ai_msg(result)}\n")

    while True:
        try:
            inp = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not inp:
            continue
        if inp.lower() == "quit":
            break

        result = run_turn_s1(app, pid, inp)
        step = result.get("current_step", "")
        label = STEP_LABELS_S1.get(step.replace("_done", ""), step)
        print(f"\n  [{label}]")
        print(f"\nTHERAPIST:\n{get_ai_msg(result)}\n")

        if result.get("current_step") == "safety_stop":
            print("  ⚠️  SESSION PAUSED — Safety concern detected")
            break

        if result.get("session_complete"):
            print("  SESSION 1 COMPLETE")
            db.print_patient_summary(pid)
            break

    db.close()
