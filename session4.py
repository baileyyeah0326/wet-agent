"""
WET Agent — Session 4 (Third Writing Session)

Same architecture as Session 1. Key differences:
  - Step 2: Discusses questionnaire score changes
  - Step 3: Between-session check-in
  - Step 4: Narrative feedback from Session 2
  - Step 5: Session 4 writing instructions (most upsetting part + life changes)
"""

from pathlib import Path
import json, re
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

from session0 import (
    WETState, _llm, _llm_json, _ctx, _get_last_human, _get_follow_up,
    _add_obs, _ai_msg, _safe_json, _safety_screen,
    _make_safety_prompt, _make_safety_judge, _safety_result_node,
    _safety_q1_router, _safety_q2_router, _safety_q3_router,
    _safety_q4_router, _safety_q5_router, _safety_q6_router,
    _safety_q6_recency_router,
    _build_json_schema, PatientDB, SAFETY_QS,
)
import session0

# ═══════════════════════════════════════════════════════
# Skill Loader
# ═══════════════════════════════════════════════════════

SKILLS_DIR_S4 = Path(__file__).parent / "skills" / "session4"


def _load_skill(filename):
    path = SKILLS_DIR_S4 / filename
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


SKILLS_S4 = {
    "s4_step1":  _load_skill("step01_welcome.md"),
    "s4_step2": _load_skill("step02_qready.md"),
    "s4_step3":  _load_skill("step03_questionnaire_discussion.md"),
    "s4_step4":  _load_skill("step04_checkin.md"),
    "s4_step5":  _load_skill("step05_narrative_feedback.md"),
    "s4_step6":  _load_skill("step06_writing_instructions.md"),
    "s4_step7":  _load_skill("step07_suds_pre.md"),
    "s4_step8":  _load_skill("step08_writing_task.md"),
    "s4_step9":  _load_skill("step09_suds_post.md"),
    "s4_step10":  _load_skill("step10_writing_discussion.md"),
    "s4_step11": _load_skill("step11_closing.md"),
}

STEP_LABELS_S4 = {
    "s4_step1":  "Step 1/11  — Welcome back",
    "s4_step2":  "Step 2/11  — Questionnaire readiness",
    "s4_step3":  "Step 3/11  — Score discussion",
    "s4_step4":  "Step 4/11  — Between-session check-in",
    "s4_step5":  "Step 5/11  — Narrative feedback",
    "s4_step6":  "Step 6/11  — Writing instructions",
    "s4_step7":  "Step 7/11  — Pre-writing SUDs",
    "s4_step8":  "Step 8/11  — Writing task",
    "s4_step9":  "Step 9/11  — Post-writing SUDs",
    "s4_step10": "Step 10/11 — Writing discussion",
    "s4_step11": "Step 11/11 — Closing",
}


# ═══════════════════════════════════════════════════════
# make_prompt / make_judge (Session 4)
# ═══════════════════════════════════════════════════════

def _parse_extract_spec(step_name):
    raw = SKILLS_S4[step_name].get("data_to_extract", "")
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
                k, v = k.strip(), v.strip()
                if k == "field": field["name"] = v
                elif k == "type": field["type"] = v
                elif k == "description": field["description"] = v
            if field["name"]:
                fields.append(field)
    return {"fields": fields, "observation": observation}


def make_prompt(step_name):
    def prompt_fn(state):
        if state.get("current_step") != step_name:
            skill = SKILLS_S4[step_name]
            task = f"[TASK] {skill.get('prompt_task', 'Continue.')}"
            notes = skill.get("clinical_notes", "")
            if notes:
                task += f"\n\nCLINICAL NOTES:\n{notes}"
            task += ("\n\nCROSS-STEP AWARENESS: Review the full conversation "
                     "history. Reference what the patient already shared.")
            if state.get("session_summaries"):
                for s in state["session_summaries"]:
                    task += f"\n\nSESSION {s.get('session', '?')} SUMMARY:\n{s.get('summary', '')}"
            if state.get("trauma_bookends"):
                task += f"\n\nBOOKENDS: {state['trauma_bookends']}"
            if state.get("pcl5_scores"):
                task += f"\n\nPCL-5 SCORE TRAJECTORY: {state['pcl5_scores']}"
            if state.get("phq9_scores"):
                task += f"\n\nPHQ-9 SCORE TRAJECTORY: {state['phq9_scores']}"
            if state.get("narratives"):
                last_narrative = state["narratives"][-1]
                task += f"\n\nPREVIOUS NARRATIVE:\n{last_narrative[:2000]}"
            content = _llm(state, task)
            label = STEP_LABELS_S4.get(step_name, step_name)
            return {"current_step": step_name, "awaiting_input": True,
                    "messages": [_ai_msg(content, label)]}
        return {"current_step": step_name, "messages": []}
    return prompt_fn


def make_judge(step_name):
    spec = _parse_extract_spec(step_name)

    def judge_fn(state):
        screen = _safety_screen(state)
        if screen["current_step"] == "safety_q1":
            return {"current_step": "safety_q1",
                    "safety_return_step": step_name, "messages": []}

        skill = SKILLS_S4[step_name]
        criteria = skill.get("judge_criteria", "pass=true if patient responded.")
        follow_guidance = skill.get("follow_up_guidance", "")
        json_schema = _build_json_schema(spec)

        task = (f"[TASK] Evaluate patient response for {step_name}.\n\n"
                f"Review ALL messages in this step.\n\n"
                f"CRITERIA:\n{criteria}\n\n"
                "ANTI-LOOPING RULE: If core criteria are met, pass=true.\n\n")
        if follow_guidance:
            task += f"FOLLOW-UP GUIDANCE:\n{follow_guidance}\n\n"
        task += f"JSON only:\n{json_schema}"

        default = {"pass": False, "follow_up": None}
        for f in spec["fields"]:
            default[f["name"]] = None

        result = _llm_json(state, task, default)

        if not result.get("pass", True):
            fu = _get_follow_up(state, result,
                f"[TASK] Respond for {step_name}. 2-3 sentences.")
            label = STEP_LABELS_S4.get(step_name, step_name)
            return {"current_step": step_name,
                    "messages": [_ai_msg(fu, label)]}

        updates = {"current_step": f"{step_name}_done", "messages": []}

        for f in spec["fields"]:
            val = result.get(f["name"])
            if val is not None:
                updates[f["name"]] = val

        if step_name == "s4_step7" and result.get("suds_pre"):
            try:
                updates["suds_pre"] = state.get("suds_pre", []) + [int(result["suds_pre"])]
            except (ValueError, TypeError):
                pass

        if step_name == "s4_step9" and result.get("suds_post"):
            try:
                updates["suds_post"] = state.get("suds_post", []) + [int(result["suds_post"])]
            except (ValueError, TypeError):
                pass

        if step_name == "s4_step8" and result.get("narrative"):
            updates["narratives"] = state.get("narratives", []) + [result["narrative"]]

        if spec["observation"]:
            obs = result.get("observation_summary", "")
            if not obs:
                obs = _get_last_human(state)[:200]
            updates["clinical_observations"] = _add_obs(state, spec["observation"], obs)

        db = session0._db
        if db is not None:
            pid = state.get("patient_id", "")
            session_num = state.get("current_session", 0)
            if spec["observation"]:
                db.add_observation(pid, session_num, spec["observation"],
                    obs if isinstance(obs, str) else json.dumps(obs))

        return updates
    return judge_fn


# ═══════════════════════════════════════════════════════
# Step 10: Closing (no judge)
# ═══════════════════════════════════════════════════════

def step11_closing(state):
    skill = SKILLS_S4["s4_step11"]
    task = f"[TASK] {skill.get('prompt_task', 'Close.')}"
    notes = skill.get("clinical_notes", "")
    if notes:
        task += f"\n\nCLINICAL NOTES:\n{notes}"
    content = _llm(state, task)

    summary = _llm_json(state, (
        "[TASK] Generate clinical summary for Session 4.\n"
        f"Pre-writing SUDs: {state.get('suds_pre', [])}\n"
        f"Post-writing SUDs: {state.get('suds_post', [])}\n"
        "JSON only:\n"
        '{"summary": "100-word summary", "next_priorities": ["p1","p2"]}'
    ), {"summary": "Session 4 completed.", "next_priorities": []})

    session_summary = {
        "session": 4,
        "summary": summary.get("summary", ""),
        "timestamp": datetime.now().isoformat(),
    }

    updates = {
        "current_step": "s4_step11_done",
        "session_complete": True,
        "messages": [_ai_msg(content, STEP_LABELS_S4.get("s4_step11", "Closing"))],
        "session_summaries": state.get("session_summaries", []) + [session_summary],
        "clinical_observations": _add_obs(state, "session4_complete", summary.get("summary", "")),
    }

    db = session0._db
    if db is not None:
        pid = state.get("patient_id", "")
        session_num = state.get("current_session", 0)
        suds_pre = state.get("suds_pre", [])
        suds_post = state.get("suds_post", [])
        narratives = state.get("narratives", [])
        db.save_session(pid, session_num,
            suds_pre=suds_pre[-1] if suds_pre else None,
            suds_post=suds_post[-1] if suds_post else None,
            narrative=narratives[-1] if narratives else None,
            session_summary=summary.get("summary", ""))
        db.add_observation(pid, session_num, "session4_complete", summary.get("summary", ""))
        db.update_patient(pid, current_session=session_num + 1)

    return updates


# ═══════════════════════════════════════════════════════
# Graph
# ═══════════════════════════════════════════════════════

def _make_judge_router(step_name, next_prompt):
    def fn(state):
        cs = state["current_step"]
        if cs == "safety_q1":
            return "safety_q1_prompt"
        if cs == f"{step_name}_done":
            return next_prompt
        return f"{step_name}_prompt"
    return fn


STEP_DEFS = [
    ("s4_step1",  make_prompt("s4_step1"),  make_judge("s4_step1")),
    ("s4_step2", make_prompt("s4_step2"), make_judge("s4_step2")),
    ("s4_step3",  make_prompt("s4_step3"),  make_judge("s4_step3")),
    ("s4_step4",  make_prompt("s4_step4"),  make_judge("s4_step4")),
    ("s4_step5",  make_prompt("s4_step5"),  make_judge("s4_step5")),
    ("s4_step6",  make_prompt("s4_step6"),  make_judge("s4_step6")),
    ("s4_step7",  make_prompt("s4_step7"),  make_judge("s4_step7")),
    ("s4_step8",  make_prompt("s4_step8"),  make_judge("s4_step8")),
    ("s4_step9",  make_prompt("s4_step9"),  make_judge("s4_step9")),
    ("s4_step10",  make_prompt("s4_step10"),  make_judge("s4_step10")),
]

SAFETY_ROUTERS_S4 = {
    "q1": _safety_q1_router, "q2": _safety_q2_router,
    "q3": _safety_q3_router, "q4": _safety_q4_router,
    "q5": _safety_q5_router, "q6": _safety_q6_router,
    "q6_recency": _safety_q6_recency_router,
}


def build_session4():
    g = StateGraph(WETState)

    for name, pfn, jfn in STEP_DEFS:
        g.add_node(f"{name}_prompt", pfn)
        g.add_node(f"{name}_judge", jfn)
    g.add_node("s4_step11_closing", step11_closing)

    for qk in SAFETY_QS:
        g.add_node(f"safety_{qk}_prompt", _make_safety_prompt(qk))
        g.add_node(f"safety_{qk}_judge", _make_safety_judge(qk))
    g.add_node("safety_result", _safety_result_node)

    g.add_edge(START, "s4_step1_prompt")

    for i, (name, _, _) in enumerate(STEP_DEFS):
        g.add_edge(f"{name}_prompt", f"{name}_judge")
        nxt = f"{STEP_DEFS[i+1][0]}_prompt" if i < len(STEP_DEFS) - 1 else "s4_step11_closing"
        g.add_conditional_edges(f"{name}_judge",
            _make_judge_router(name, nxt),
            {nxt: nxt, f"{name}_prompt": f"{name}_prompt",
             "safety_q1_prompt": "safety_q1_prompt"})

    g.add_edge("s4_step11_closing", END)

    for qk in SAFETY_QS:
        g.add_edge(f"safety_{qk}_prompt", f"safety_{qk}_judge")

    for qk in SAFETY_QS:
        router = SAFETY_ROUTERS_S4[qk]
        possible = set()
        if qk == "q1": possible = {"safety_q1_prompt", "safety_q2_prompt"}
        elif qk == "q2": possible = {"safety_q2_prompt", "safety_q3_prompt", "safety_q6_prompt"}
        elif qk == "q3": possible = {"safety_q3_prompt", "safety_q4_prompt"}
        elif qk == "q4": possible = {"safety_q4_prompt", "safety_q5_prompt"}
        elif qk == "q5": possible = {"safety_q5_prompt", "safety_q6_prompt"}
        elif qk == "q6": possible = {"safety_q6_prompt", "safety_q6_recency_prompt", "safety_result"}
        elif qk == "q6_recency": possible = {"safety_q6_recency_prompt", "safety_result"}
        g.add_conditional_edges(f"safety_{qk}_judge", router, {d: d for d in possible})

    all_prompts = {f"{s[0]}_prompt": f"{s[0]}_prompt" for s in STEP_DEFS}
    all_prompts["safety_stop"] = END

    def _safety_result_router(state):
        if state.get("current_step") == "safety_stop":
            return "safety_stop"
        return f"{state.get('safety_return_step', 's4_step1')}_prompt"

    g.add_conditional_edges("safety_result", _safety_result_router, all_prompts)
    return g


# ═══════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════

DB_DIR = Path(__file__).parent / "data"


def create_app_s4():
    import sqlite3
    DB_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_DIR / "checkpoints.db"), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    db = PatientDB(str(DB_DIR / "patients.db"))
    session0._db = db

    graph = build_session4()
    interrupt_nodes = [f"{s[0]}_prompt" for s in STEP_DEFS]
    interrupt_nodes += [f"safety_{qk}_prompt" for qk in SAFETY_QS]
    app = graph.compile(checkpointer=checkpointer, interrupt_after=interrupt_nodes)
    return app, db


def start_session4(app, db, pid):
    config = {"configurable": {"thread_id": f"patient_{pid}_s4"}}

    existing = app.get_state(config)
    if existing and existing.values and existing.values.get("current_step"):
        if existing.values.get("session_complete"):
            return existing.values
        return existing.values

    patient = db.get_patient(pid)
    s_summaries = db.get_session_summaries(pid)
    s_observations = db.get_observations(pid)
    s_avoidance = db.get_avoidance_patterns(pid)

    # Load previous narratives and scores
    prev_sessions = db.get_sessions(pid)
    prev_narratives = [s.get("narrative", "") for s in prev_sessions
                       if s.get("narrative")]
    prev_pcl5 = [s.get("pcl5_score") for s in prev_sessions
                 if s.get("pcl5_score") is not None]
    prev_phq9 = [s.get("phq9_score") for s in prev_sessions
                 if s.get("phq9_score") is not None]

    return app.invoke({
        "current_session": 4, "current_step": "", "session_complete": False,
        "awaiting_input": False, "patient_id": pid,
        "index_trauma": patient.get("index_trauma", "") if patient else "",
        "trauma_described": patient.get("trauma_described", False) if patient else False,
        "trauma_bookends": patient.get("trauma_bookends", {}) if patient else {},
        "therapy_goals": patient.get("therapy_goals", []) if patient else [],
        "reason_for_therapy": patient.get("reason_for_therapy", "") if patient else "",
        "pcl5_scores": prev_pcl5, "phq9_scores": prev_phq9,
        "suds_pre": [], "suds_post": [],
        "narratives": prev_narratives,
        "narrative_feedback": [], "messages": [], "modality": "",
        "session_summaries": [{"session": s["session"], "summary": s["summary"]}
                              for s in s_summaries],
        "clinical_observations": [{"session": o["session_num"], "type": o["obs_type"],
                                   "content": o["content"]} for o in s_observations],
        "avoidance_patterns": [{"session": a["session_num"], "pattern": a["pattern"]}
                               for a in s_avoidance],
        "safety_answers": {}, "safety_risk": "", "safety_return_step": "",
    }, config=config)


def run_turn_s4(app, pid, message):
    config = {"configurable": {"thread_id": f"patient_{pid}_s4"}}
    app.update_state(config, {"messages": [HumanMessage(content=message)]})
    return app.invoke(None, config=config)


def get_ai_msg(result):
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage):
            return msg.content
    return ""