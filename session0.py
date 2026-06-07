"""
WET Agent — Session 0 (Skill-file driven, unified architecture)

All clinical content lives in skills/session0/*.md files.
Clinical experts edit .md files. Developers edit this code.

Architecture:
  - make_prompt(step_name) → reads Prompt Task from skill file
  - make_judge(step_name)  → reads Judge Criteria + Data to Extract from skill file
  - Both are fully generic — no per-step custom code needed
  - Step 9 skip logic is the ONLY special case (conditional skip)
"""

from typing import TypedDict, Annotated
from datetime import datetime
from pathlib import Path
import json, operator, re

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, BaseMessage,
)
from langchain_openai import ChatOpenAI
from patient_db import PatientDB

import logging
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
import os
# API key from environment or Streamlit secrets
if "OPENAI_API_KEY" not in os.environ:
    try:
        import streamlit as st
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

llm = ChatOpenAI(model="gpt-5.5", temperature=0.3)


# ═══════════════════════════════════════════════════════════════════
# Skill Loader
# ═══════════════════════════════════════════════════════════════════

SKILLS_DIR = Path(__file__).parent / "skills" / "session0"


def _load_skill(filename):
    path = SKILLS_DIR / filename
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


def _load_all_skills():
    files = [
        ("step1",  "step01_greetings.md"),
        ("step2",  "step02_reason.md"),
        ("step3",  "step03_feelings.md"),
        ("step4",  "step04_threat_fear_arousal.md"),
        ("step5",  "step05_trauma_concept.md"),
        ("step6",  "step06_avoidance.md"),
        ("step7",  "step07_symptoms.md"),
        ("step8",  "step08_introduce_wet.md"),
        ("step9",  "step09_identify_trauma.md"),
        ("step10", "step10_impact_goals.md"),
        ("step11", "step11_wet_details.md"),
        ("step12", "step12_bookends.md"),
        ("step13", "step13_closing.md"),
    ]
    return {name: _load_skill(fn) for name, fn in files}


SKILLS = _load_all_skills()


# ═══════════════════════════════════════════════════════════════════
# Data Extract Parser
# ═══════════════════════════════════════════════════════════════════

def _parse_extract_spec(step_name):
    """Parse ## Data to Extract into structured spec.
    
    Supported lines:
      field: name | type: string/list/boolean/enum | description: ...
      observation: obs_type
      None
    
    Field names should match WETState keys directly — no mapping needed.
    """
    raw = SKILLS[step_name].get("data_to_extract", "")
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
                if k == "field":
                    field["name"] = v
                elif k == "type":
                    field["type"] = v
                elif k == "description":
                    field["description"] = v
                elif k == "nullable":
                    field["nullable"] = v.lower() == "true"
                elif k == "values":
                    field["values"] = [x.strip() for x in v.split(",")]
            if field["name"]:
                fields.append(field)
        else:
            print(f"  ⚠️  [{step_name}] Unrecognized line in Data to Extract: '{line}'")
            print(f"       Must start with 'field:', 'observation:', or 'None'")

    return {"fields": fields, "observation": observation}


def _build_json_schema(spec):
    parts = ['"pass": true or false',
             '"follow_up": "if pass=false: your follow-up. null if true"']
    for f in spec["fields"]:
        if f["type"] == "list":
            parts.append(f'"{f["name"]}": [{f["description"]}]')
        elif f["type"] == "enum":
            vals = " or ".join(f'"{v}"' for v in f["values"])
            parts.append(f'"{f["name"]}": {vals}')
        elif f["type"] == "boolean":
            parts.append(f'"{f["name"]}": true or false')
        else:
            null = ", or null" if f["nullable"] else ""
            parts.append(f'"{f["name"]}": "{f["description"]}{null}"')
    # Always ask LLM to generate a clinical observation summary
    if spec["observation"]:
        parts.append(
            '"observation_summary": "1-2 sentence clinical observation '
            'summarizing what the patient shared in this step and any '
            'clinically relevant details. Write as a therapist note, '
            'not a transcript."')
    return "{\n  " + ",\n  ".join(parts) + "\n}"



# ═══════════════════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════════════════

class WETState(TypedDict):
    current_session: int
    current_step: str
    session_complete: bool
    awaiting_input: bool
    patient_id: str
    index_trauma: str
    trauma_described: bool
    trauma_bookends: dict
    therapy_goals: list[str]
    reason_for_therapy: str
    pcl5_scores: list[int]
    phq9_scores: list[int]
    suds_pre: list[int]
    suds_post: list[int]
    narratives: list[str]
    narrative_feedback: list[dict]
    messages: Annotated[list[BaseMessage], operator.add]
    modality: str
    session_summaries: list[dict]
    clinical_observations: list[dict]
    avoidance_patterns: list[dict]
    safety_answers: dict          # screening Q&A results
    safety_risk: str              # LOW / MODERATE / HIGH
    safety_return_step: str       # which therapy step to return to after LOW risk


# ═══════════════════════════════════════════════════════════════════
# LLM utilities
# ═══════════════════════════════════════════════════════════════════

def _get_last_human(state):
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""

def _safe_json(text, default):
    try:
        return json.loads(text.replace("```json","").replace("```","").strip())
    except (json.JSONDecodeError, AttributeError):
        print("JSONDecodeError")
        return default

SYSTEM_PROMPT = """You are a compassionate, clinically trained Written
Exposure Therapy (WET) therapist conducting Session 0.

STYLE: Warm, empathetic, professional. Simple language. Natural and
conversational. Validate feelings. Never push disclosure. Adapt to
what the patient said. Keep responses focused — not too long.

SAFETY PROTOCOL:
If the patient expresses suicidal ideation, self-harm intent, or intent
to harm others, acknowledge what they said calmly. Do NOT continue the
therapy session. The system will handle escalation to a human clinician.

CONTEXT:
{context}
"""

def _ctx(state):
    parts = []
    if state.get("reason_for_therapy"):
        parts.append(f"Reason: {state['reason_for_therapy']}")
    if state.get("index_trauma"):
        parts.append(f"Trauma: {state['index_trauma']}")
    if state.get("trauma_described"):
        parts.append("Trauma has been described.")
    if state.get("therapy_goals"):
        parts.append(f"Goals: {', '.join(state['therapy_goals'])}")
    if state.get("trauma_bookends"):
        parts.append(f"Bookends: {state['trauma_bookends']}")
    for o in state.get("clinical_observations", [])[-3:]:
        parts.append(f"[{o.get('type','')}] {o.get('content','')[:100]}")
    return "\n".join(parts) if parts else "Session just started."

def _llm(state, task):
    return llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT.format(context=_ctx(state))),
        *state.get("messages", []),
        HumanMessage(content=task),
    ]).content

def _llm_json(state, task, default):
    return _safe_json(_llm(state, task), default)

def _get_follow_up(state, result, fallback_task):
    fu = result.get("follow_up")
    return fu if fu else _llm(state, fallback_task)

def _add_obs(state, obs_type, content):
    return state.get("clinical_observations", []) + [{
        "session": state.get("current_session", 0),
        "type": obs_type,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }]


# ═══════════════════════════════════════════════════════════════════
# Suicide Risk Assessment — Subgraph
# ═══════════════════════════════════════════════════════════════════

SCREENING_QUESTIONS = [
    ("q1", "I want to ask you something important, and I appreciate your honesty. Have you wished you were dead, or wished you could go to sleep and not wake up?"),
    ("q2", "Have you actually had any thoughts of killing yourself?"),
    ("q3", "Have you been thinking about how you might do it?"),
    ("q4", "Have you had these thoughts and had some intention of acting on them?"),
    ("q5", "Have you started to work out or worked out the details of a plan? Do you intend to carry it out?"),
    ("q6", "Have you ever done anything, started to do anything, or prepared to do anything to end your life? That could include things like collecting pills, obtaining a weapon, giving away valuables, writing a note, or actually attempting to harm yourself."),
    ("q6_recency", "How long ago did you do any of these things? Was it over a year ago, between three months and a year ago, or within the last three months?"),
]

SCREENING_MAP = dict(SCREENING_QUESTIONS)


def _classify_risk(answers: dict) -> str:
    """Classify risk level from screening answers."""
    if answers.get("q5", False):
        return "HIGH"
    if answers.get("q6", False) and answers.get("q6_recency") in ("within_3_months", "unclear"):
        return "HIGH"
    if answers.get("q3", False) or answers.get("q4", False):
        return "MODERATE"
    return "LOW"


# ── Safety screening node: detect trigger in judge ──

def _safety_screen(state):
    """Check if the patient's last message triggers safety screening."""
    last_msg = _get_last_human(state)
    if not last_msg:
        return {"current_step": state.get("current_step", "")}

    result = _llm_json(state, (
        "[TASK] Safety screening. Does the patient's message contain "
        "warning signs related to suicidality, self-harm, or intent "
        "to harm others?\n\n"
        f'Patient said: "{last_msg}"\n\n'
        "Trigger examples:\n"
        '- "I wish I wouldn\'t wake up"\n'
        '- "Everyone would be better without me"\n'
        '- "I\'m tired of living" / "I don\'t care anymore"\n'
        '- "I want to die" / "I want to disappear"\n'
        '- Mentions of suicide, killing self, ending life\n'
        '- Intent to harm others\n\n'
        "NOT triggers: frustration, anger about trauma, "
        '"this makes me so angry"\n\n'
        'JSON only:\n{"safety_flag": true or false}'
    ), {"safety_flag": False})

    flagged = result.get("safety_flag")
    if flagged == True or flagged == "true":
        return {"current_step": "safety_q1"}
    return {"current_step": state.get("current_step", "")}


# ── Safety question nodes (prompt + judge for each Q) ──

def _make_safety_prompt(q_key):
    """Create prompt node for a screening question."""
    def fn(state):
        if state.get("current_step") != q_key:
            question = SCREENING_MAP[q_key]
            return {"current_step": q_key,
                    "messages": [AIMessage(content=question)]}
        return {"current_step": q_key, "messages": []}
    return fn


def _make_safety_judge(q_key):
    """Create judge node for a screening question.
    LLM interprets patient's free-form answer as yes/no/unclear.
    If unclear, generates a follow-up and loops back."""
    def fn(state):
        last_msg = _get_last_human(state)
        question = SCREENING_MAP[q_key]
        answers = dict(state.get("safety_answers", {}))

        if q_key == "q6_recency":
            result = _llm_json(state, (
                "[TASK] The patient was asked about recency of "
                "suicidal behavior:\n"
                f'"{question}"\n'
                f'Patient answered: "{last_msg}"\n\n'
                "Classify the recency. If the patient's answer is "
                "unclear or doesn't address the question, set "
                'recency to "unclear".\n\n'
                'JSON only:\n'
                '{\n'
                '  "recency": "within_3_months" or "3_months_to_1_year" '
                'or "over_a_year" or "unclear",\n'
                '  "follow_up": "if unclear: a gentle follow-up question '
                'to clarify. null if clear enough to classify"\n'
                '}'
            ), {"recency": "unclear", "follow_up": None})

            recency = result.get("recency", "unclear")

            if recency == "unclear":
                fu = result.get("follow_up") or (
                    "I want to make sure I understand. Could you help "
                    "me with roughly when that was — was it recently, "
                    "in the past few months, or longer ago than that?")
                return {"current_step": q_key,
                        "messages": [AIMessage(content=fu)]}

            answers["q6_recency"] = recency
            risk = _classify_risk(answers)
            return {"current_step": f"{q_key}_done",
                    "safety_answers": answers,
                    "safety_risk": risk}
        else:
            result = _llm_json(state, (
                "[TASK] The patient was asked:\n"
                f'"{question}"\n'
                f'Patient answered: "{last_msg}"\n\n'
                "Does the patient mean YES, NO, or is the answer "
                "UNCLEAR?\n"
                "Patients may say 'sometimes', 'I guess', 'not really', "
                "'kind of', or give unrelated responses.\n"
                "- If the answer clearly means yes → 'yes'\n"
                "- If the answer clearly means no → 'no'\n"
                "- If the answer is evasive, off-topic, or you genuinely "
                "cannot determine → 'unclear'\n\n"
                'JSON only:\n'
                '{\n'
                '  "answer": "yes" or "no" or "unclear",\n'
                '  "follow_up": "if unclear: a gentle, empathetic follow-up '
                'to help the patient answer more directly. null if yes or no"\n'
                '}'
            ), {"answer": "unclear", "follow_up": None})

            answer = result.get("answer", "unclear").lower()

            if answer == "unclear":
                fu = result.get("follow_up") or (
                    "I appreciate you sharing that. To make sure I "
                    "understand, could you tell me a bit more about "
                    "what you mean?")
                return {"current_step": q_key,
                        "messages": [AIMessage(content=fu)]}

            is_yes = answer == "yes"
            answers[q_key] = is_yes
            risk = _classify_risk(answers)
            return {"current_step": f"{q_key}_done",
                    "safety_answers": answers,
                    "safety_risk": risk}
    return fn


def _safety_result_node(state):
    """Final node — generate response based on risk level."""
    risk = state.get("safety_risk", "LOW")
    answers = state.get("safety_answers", {})

    # Log to DB
    if _db is not None:
        pid = state.get("patient_id", "")
        session_num = state.get("current_session", 0)
        _db.add_observation(pid, session_num,
            f"safety_{risk}",
            f"Risk: {risk}. Answers: {answers}.")

    if risk == "LOW":
        msg = _llm(state, (
            "[TASK] The patient triggered a safety screening but the "
            "risk level is LOW. Briefly acknowledge their feelings, "
            "validate them, and gently return to the therapy session. "
            "2-3 sentences."
        ))
        return_step = state.get("safety_return_step", "step1")
        return {
            "current_step": return_step,
            "messages": [AIMessage(content=msg)],
            "safety_answers": {},
            "safety_risk": "",
        }
    else:
        msg = (
            "Thank you for being honest with me — that takes real "
            "courage. Based on what you've shared, I want to make "
            "sure you get the right support right now. Please reach "
            "out to the 988 Suicide & Crisis Lifeline — you can call "
            "or text 988. You can also text HOME to 741741 to reach "
            "the Crisis Text Line. I'm going to connect you with a "
            "human clinician who can support you."
        )
        return {
            "current_step": "safety_stop",
            "session_complete": True,
            "messages": [AIMessage(content=msg)],
        }


# ── Safety routing logic ──

def _safety_q1_router(state):
    if state.get("current_step") == "q1":
        return "safety_q1_prompt"  # unclear → loop back
    return "safety_q2_prompt"

def _safety_q2_router(state):
    if state.get("current_step") == "q2":
        return "safety_q2_prompt"
    if state.get("safety_answers", {}).get("q2"):
        return "safety_q3_prompt"
    return "safety_q6_prompt"

def _safety_q3_router(state):
    if state.get("current_step") == "q3":
        return "safety_q3_prompt"
    return "safety_q4_prompt"

def _safety_q4_router(state):
    if state.get("current_step") == "q4":
        return "safety_q4_prompt"
    return "safety_q5_prompt"

def _safety_q5_router(state):
    if state.get("current_step") == "q5":
        return "safety_q5_prompt"
    return "safety_q6_prompt"

def _safety_q6_router(state):
    if state.get("current_step") == "q6":
        return "safety_q6_prompt"
    if state.get("safety_answers", {}).get("q6"):
        return "safety_q6_recency_prompt"
    return "safety_result"

def _safety_q6_recency_router(state):
    if state.get("current_step") == "q6_recency":
        return "safety_q6_recency_prompt"
    return "safety_result"


# ═══════════════════════════════════════════════════════════════════
# Unified make_prompt / make_judge
# ═══════════════════════════════════════════════════════════════════

def make_prompt(step_name):
    def prompt_fn(state):
        if state.get("current_step") != step_name:
            skill = SKILLS[step_name]
            task = f"[TASK] {skill.get('prompt_task', 'Continue.')}"
            notes = skill.get("clinical_notes", "")
            if notes:
                task += f"\n\nCLINICAL NOTES:\n{notes}"
            content = _llm(state, task)
            return {"current_step": step_name, "awaiting_input": True,
                    "messages": [AIMessage(content=content)]}
        return {"current_step": step_name, "messages": []}
    return prompt_fn


# Module-level DB reference — set by create_app()
_db: "PatientDB | None" = None


def make_judge(step_name):
    spec = _parse_extract_spec(step_name)

    def judge_fn(state):
        # ── Safety screen — route to assessment subgraph if triggered ──
        screen = _safety_screen(state)
        if screen["current_step"] == "safety_q1":
            return {"current_step": "safety_q1",
                    "safety_return_step": step_name,
                    "messages": []}

        # ── Normal judge logic ──
        skill = SKILLS[step_name]
        criteria = skill.get("judge_criteria", "pass=true if patient responded.")
        follow_guidance = skill.get("follow_up_guidance", "")
        json_schema = _build_json_schema(spec)

        task = (f"[TASK] Evaluate patient response for {step_name}.\n\n"
                f"Review ALL messages in this step.\n\n"
                f"CRITERIA:\n{criteria}\n\n")
        if follow_guidance:
            task += (
                f"FOLLOW-UP GUIDANCE (if pass=false):\n{follow_guidance}\n\n"
                "IMPORTANT: The follow_up field must be a NATURAL therapist "
                "response BASED ON the guidance above — do NOT copy the "
                "guidance text. Write as if you are speaking directly to "
                "the patient in first person.\n\n"
                "The follow_up message MUST end with an open question or "
                "a clear invitation that gives the patient something to "
                "respond to. Do NOT end with a statement that closes the "
                "conversation — the patient needs to know what to say next.\n\n"
            )
        task += f"JSON only:\n{json_schema}"

        default_pass = False
        default = {"pass": default_pass, "follow_up": None}
        for f in spec["fields"]:
            default[f["name"]] = [] if f["type"] == "list" else None

        result = _llm_json(state, task, default)

        if not result.get("pass", True):
            fu = _get_follow_up(state, result,
                f"[TASK] Respond for {step_name}. Guide. 2-3 sentences.")
            return {"current_step": step_name,
                    "messages": [AIMessage(content=fu)]}

        # ── PASS: write extracted fields directly to state ──
        updates = {"current_step": f"{step_name}_done", "messages": []}

        # Field names = state keys. Write directly.
        for f in spec["fields"]:
            val = result.get(f["name"])
            if val is not None:
                updates[f["name"]] = val

        # Derived fields (hardcoded — too complex for DSL)
        # step2: trauma_described = category is describes_trauma AND index_trauma exists
        if result.get("category") == "describes_trauma" and result.get("index_trauma"):
            updates["trauma_described"] = True

        # step9: if index_trauma was extracted, trauma_described = True
        if step_name == "step9" and result.get("index_trauma"):
            updates["trauma_described"] = True

        # step12: compose trauma_bookends from individual fields
        if result.get("beginning") and result.get("end"):
            updates["trauma_bookends"] = {
                "beginning": result.get("beginning", ""),
                "end": result.get("end", ""),
                "duration": result.get("duration", ""),
            }

        # step6: convert avoidance_patterns list[str] → list[dict] with metadata
        # (overrides the generic list[str] written above)
        if result.get("avoidance_patterns") and isinstance(result["avoidance_patterns"], list):
            entries = [
                {"session": state.get("current_session", 0),
                 "pattern": p,
                 "timestamp": datetime.now().isoformat()}
                for p in result["avoidance_patterns"]
            ]
            updates["avoidance_patterns"] = \
                state.get("avoidance_patterns", []) + entries

        # Store observation (LLM-generated summary, not raw patient text)
        if spec["observation"]:
            obs = result.get("observation_summary", "")
            if not obs:
                obs = _get_last_human(state)[:200]
            updates["clinical_observations"] = _add_obs(
                state, spec["observation"], obs)

        # ── Real-time DB write ──
        if _db is not None:
            pid = state.get("patient_id", "")
            session_num = state.get("current_session", 0)

            db_updates = {k: v for k, v in updates.items()
                          if k in ("index_trauma", "trauma_described",
                                   "trauma_bookends", "therapy_goals",
                                   "reason_for_therapy")}
            if db_updates:
                _db.update_patient(pid, **db_updates)

            # Write avoidance patterns to DB
            if result.get("avoidance_patterns") and isinstance(result["avoidance_patterns"], list):
                for p in result["avoidance_patterns"]:
                    _db.add_avoidance_pattern(pid, session_num, p)

            if spec["observation"]:
                _db.add_observation(pid, session_num,
                    spec["observation"],
                    obs if isinstance(obs, str) else json.dumps(obs))

        return updates
    return judge_fn


# Step 9 no longer needs custom code — skip logic is in step8_judge router


# ═══════════════════════════════════════════════════════════════════
# Step 13: closing (no judge — standalone function)
# ═══════════════════════════════════════════════════════════════════

def step13_closing(state):
    skill = SKILLS["step13"]
    task = f"[TASK] {skill.get('prompt_task', 'Close.')}"
    notes = skill.get("clinical_notes", "")
    if notes:
        task += f"\n\nCLINICAL NOTES:\n{notes}"
    content = _llm(state, task)

    # Generate session summary for cross-session memory
    summary = _llm_json(state, (
        "[TASK] Generate a clinical session summary for Session 0.\n\n"
        "This summary will be injected into future sessions' system "
        "prompts so the therapist has continuity.\n\n"
        f"Patient's trauma: {state.get('index_trauma','')}\n"
        f"Therapy goals: {state.get('therapy_goals',[])}\n"
        f"Bookends: {state.get('trauma_bookends',{})}\n"
        f"Reason for therapy: {state.get('reason_for_therapy','')}\n\n"
        "Review the full conversation and generate:\n"
        "JSON only:\n"
        "{\n"
        '  "summary": "A ~200-word clinical summary covering: '
        "reason for therapy, trauma identified, patient's emotional "
        "state, key avoidance patterns, therapy goals, bookends, "
        "rapport level, and priorities for Session 1.\",\n"
        '  "rapport_level": "good" or "cautious" or "resistant",\n'
        '  "session1_priorities": ["priority1", "priority2", ...]\n'
        "}"
    ), {"summary": "Session 0 completed.",
        "rapport_level": "good", "session1_priorities": []})

    session_summary = {
        "session": 0,
        "summary": summary.get("summary", ""),
        "rapport_level": summary.get("rapport_level", ""),
        "session1_priorities": summary.get("session1_priorities", []),
        "timestamp": datetime.now().isoformat(),
    }

    summary_text = summary.get("summary", "Session 0 completed.")
    completion_note = (
        f"Session 0 completed. "
        f"Rapport: {summary.get('rapport_level', 'good')}. "
        f"Priorities for S1: {summary.get('session1_priorities', [])}"
    )

    updates = {
        "current_step": "step13_done",
        "session_complete": True,
        "messages": [AIMessage(content=content)],
        "session_summaries": state.get("session_summaries", []) + [session_summary],
        "clinical_observations": _add_obs(
            state, "session_complete", completion_note),
    }

    if _db is not None:
        pid = state.get("patient_id", "")
        session_num = state.get("current_session", 0)
        _db.save_session(pid, session_num,
                         session_summary=summary_text)
        _db.add_observation(pid, session_num,
            "session_complete", completion_note)
        _db.update_patient(pid, current_session=session_num + 1)

    return updates


# ═══════════════════════════════════════════════════════════════════
# Graph
# ═══════════════════════════════════════════════════════════════════

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
    ("step1",  make_prompt("step1"),  make_judge("step1")),
    ("step2",  make_prompt("step2"),  make_judge("step2")),
    ("step3",  make_prompt("step3"),  make_judge("step3")),
    ("step4",  make_prompt("step4"),  make_judge("step4")),
    ("step5",  make_prompt("step5"),  make_judge("step5")),
    ("step6",  make_prompt("step6"),  make_judge("step6")),
    ("step7",  make_prompt("step7"),  make_judge("step7")),
    ("step8",  make_prompt("step8"),  make_judge("step8")),
    ("step9",  make_prompt("step9"),  make_judge("step9")),
    ("step10", make_prompt("step10"), make_judge("step10")),
    ("step11", make_prompt("step11"), make_judge("step11")),
    ("step12", make_prompt("step12"), make_judge("step12")),
]

# Safety screening question keys (for building subgraph)
SAFETY_QS = ["q1", "q2", "q3", "q4", "q5", "q6", "q6_recency"]

SAFETY_ROUTERS = {
    "q1": _safety_q1_router,
    "q2": _safety_q2_router,
    "q3": _safety_q3_router,
    "q4": _safety_q4_router,
    "q5": _safety_q5_router,
    "q6": _safety_q6_router,
    "q6_recency": _safety_q6_recency_router,
}


def build_session0():
    g = StateGraph(WETState)

    # ── Main therapy nodes ──
    for name, pfn, jfn in STEP_DEFS:
        g.add_node(f"{name}_prompt", pfn)
        g.add_node(f"{name}_judge", jfn)
    g.add_node("step13_closing", step13_closing)

    # ── Safety subgraph nodes ──
    for qk in SAFETY_QS:
        g.add_node(f"safety_{qk}_prompt", _make_safety_prompt(qk))
        g.add_node(f"safety_{qk}_judge", _make_safety_judge(qk))
    g.add_node("safety_result", _safety_result_node)

    # ── Main therapy edges ──
    g.add_edge(START, "step1_prompt")

    for i, (name, _, _) in enumerate(STEP_DEFS):
        g.add_edge(f"{name}_prompt", f"{name}_judge")

        if i < len(STEP_DEFS) - 1:
            nxt = f"{STEP_DEFS[i+1][0]}_prompt"
        else:
            nxt = "step13_closing"

        if name == "step8":
            def _step8_router(state):
                cs = state["current_step"]
                if cs == "safety_q1":
                    return "safety_q1_prompt"
                if cs != "step8_done":
                    return "step8_prompt"
                if state.get("trauma_described", False):
                    return "step10_prompt"
                return "step9_prompt"
            g.add_conditional_edges("step8_judge", _step8_router,
                {"step8_prompt": "step8_prompt",
                 "step9_prompt": "step9_prompt",
                 "step10_prompt": "step10_prompt",
                 "safety_q1_prompt": "safety_q1_prompt"})
        else:
            g.add_conditional_edges(f"{name}_judge",
                _make_judge_router(name, nxt),
                {nxt: nxt,
                 f"{name}_prompt": f"{name}_prompt",
                 "safety_q1_prompt": "safety_q1_prompt"})

    g.add_edge("step13_closing", END)

    # ── Safety subgraph edges ──
    for qk in SAFETY_QS:
        g.add_edge(f"safety_{qk}_prompt", f"safety_{qk}_judge")

    # Safety routing: each judge → router → next question or result
    # Build destination sets for each router
    safety_dests = {f"safety_{qk}_prompt" for qk in SAFETY_QS}
    safety_dests.add("safety_result")

    for qk in SAFETY_QS:
        router = SAFETY_ROUTERS[qk]
        possible = set()
        if qk == "q1":
            possible = {"safety_q1_prompt", "safety_q2_prompt"}
        elif qk == "q2":
            possible = {"safety_q2_prompt", "safety_q3_prompt", "safety_q6_prompt"}
        elif qk == "q3":
            possible = {"safety_q3_prompt", "safety_q4_prompt"}
        elif qk == "q4":
            possible = {"safety_q4_prompt", "safety_q5_prompt"}
        elif qk == "q5":
            possible = {"safety_q5_prompt", "safety_q6_prompt"}
        elif qk == "q6":
            possible = {"safety_q6_prompt", "safety_q6_recency_prompt", "safety_result"}
        elif qk == "q6_recency":
            possible = {"safety_q6_recency_prompt", "safety_result"}

        g.add_conditional_edges(
            f"safety_{qk}_judge", router,
            {d: d for d in possible})

    # Safety result → conditional: LOW returns to therapy, MOD/HIGH → END
    # Build all possible return destinations
    all_therapy_prompts = {f"{s[0]}_prompt": f"{s[0]}_prompt" for s in STEP_DEFS}
    all_therapy_prompts["safety_stop"] = END

    def _safety_result_router(state):
        if state.get("current_step") == "safety_stop":
            return "safety_stop"
        # LOW risk: return to the therapy step prompt
        return_step = state.get("safety_return_step", "step1")
        return f"{return_step}_prompt"

    g.add_conditional_edges("safety_result", _safety_result_router,
        all_therapy_prompts)

    return g


# ═══════════════════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════════════════

DB_DIR = Path(__file__).parent / "data"


def create_app():
    global _db
    DB_DIR.mkdir(exist_ok=True)

    import sqlite3
    conn = sqlite3.connect(str(DB_DIR / "checkpoints.db"),
                           check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    db = PatientDB(str(DB_DIR / "patients.db"))
    _db = db   # make accessible to make_judge

    graph = build_session0()

    # interrupt_after: all therapy prompts + all safety prompts
    interrupt_nodes = [f"{s[0]}_prompt" for s in STEP_DEFS]
    interrupt_nodes += [f"safety_{qk}_prompt" for qk in SAFETY_QS]

    app = graph.compile(checkpointer=checkpointer,
        interrupt_after=interrupt_nodes)

    return app, db

def start_session(app, db, pid):
    """Start a new session. Creates patient in DB if not exists.
    If patient already has a partially completed session, resumes it."""
    config = {"configurable": {"thread_id": f"patient_{pid}_s0"}}

    # Check if we can resume an existing session
    existing = app.get_state(config)
    if existing and existing.values and existing.values.get("current_step"):
        if existing.values.get("session_complete"):
            print(f"  Session 0 already complete for {pid}.")
            return existing.values
        print(f"  Resuming session for {pid} at {existing.values['current_step']}")
        return existing.values

    # New session — create patient in DB
    db.create_patient(pid)

    return app.invoke({
        "current_session": 0, "current_step": "",
        "session_complete": False, "awaiting_input": False,
        "patient_id": pid, "index_trauma": "",
        "trauma_described": False, "trauma_bookends": {},
        "therapy_goals": [], "reason_for_therapy": "",
        "pcl5_scores": [], "phq9_scores": [],
        "suds_pre": [], "suds_post": [],
        "narratives": [], "narrative_feedback": [],
        "messages": [], "modality": "",
        "session_summaries": [], "clinical_observations": [],
        "avoidance_patterns": [],
        "safety_answers": {},
        "safety_risk": "",
        "safety_return_step": "",
    }, config=config)

def run_turn(app, pid, message):
    config = {"configurable": {"thread_id": f"patient_{pid}_s0"}}
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

STEP_LABELS = {
    "step1":  "Step 1/13  — Greetings",
    "step2":  "Step 2/13  — Reason for therapy",
    "step3":  "Step 3/13  — Current feelings",
    "step4":  "Step 4/13  — Psychoed: threat/fear/arousal",
    "step5":  "Step 5/13  — Psychoed: trauma concept",
    "step6":  "Step 6/13  — Psychoed: avoidance",
    "step7":  "Step 7/13  — Additional symptoms",
    "step8":  "Step 8/13  — Introduce WET",
    "step9":  "Step 9/13  — Identify trauma",
    "step10": "Step 10/13 — PTSD impact & goals",
    "step11": "Step 11/13 — WET details & Q&A",
    "step12": "Step 12/13 — Trauma bookends",
    "step13": "Step 13/13 — Closing",
}

def _print_step(result):
    step = result.get("current_step", "")
    base = step.replace("_done", "")
    label = STEP_LABELS.get(base, step)
    print(f"  [{label}]")


def _print_state(result):
    """Print extracted state after every turn."""
    print("  ┌─── State ───────────────────────────────────")
    print(f"  │ step:             {result.get('current_step', '')}")
    print(f"  │ reason_for_therapy: {result.get('reason_for_therapy', '') or '—'}")
    print(f"  │ trauma_described:  {result.get('trauma_described', False)}")
    print(f"  │ index_trauma:      {result.get('index_trauma', '') or '—'}")
    print(f"  │ therapy_goals:     {result.get('therapy_goals', []) or '—'}")
    print(f"  │ trauma_bookends:   {result.get('trauma_bookends', {}) or '—'}")

    # Avoidance patterns
    av = result.get("avoidance_patterns", [])
    if av:
        patterns = [a.get("pattern", "") for a in av]
        print(f"  │ avoidance_patterns: {patterns}")
    else:
        print(f"  │ avoidance_patterns: —")

    # Session summaries
    ss = result.get("session_summaries", [])
    if ss:
        latest = ss[-1]
        print(f"  │ session_summaries: {len(ss)} (latest: {latest.get('summary','')[:80]}...)")
    else:
        print(f"  │ session_summaries: —")

    # Observations
    obs = result.get("clinical_observations", [])
    print(f"  │ observations:      {len(obs)}", end="")
    if obs:
        latest = obs[-1]
        print(f" (latest: [{latest.get('type','')}] {latest.get('content','')[:60]})")
    else:
        print()

    print(f"  │ messages:          {len(result.get('messages', []))}")
    print(f"  │ session_complete:  {result.get('session_complete', False)}")
    print("  └────────────────────────────────────────────")

if __name__ == "__main__":
    print("=" * 60)
    print("  WET Agent — Session 0 (Persistent)")
    print(f"  Skills: {SKILLS_DIR}")
    print(f"  Data:   {DB_DIR}")
    print("=" * 60)

    app, db = create_app()

    # Ask for patient ID
    pid = input("  Enter Patient ID: ").strip()
    if not pid:
        pid = "P001"
        print(f"  Using default: {pid}")
    print()

    # Admin mode — management only, no session
    if pid == "admin":
        print("  Admin mode. Commands: reset, reset patient, db, quit\n")
        while True:
            try:
                inp = input("ADMIN: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not inp:
                continue
            if inp.lower() == "quit":
                break
            if inp.lower() == "db":
                target = input("  Enter Patient ID to view: ").strip()
                if target:
                    db.print_patient_summary(target)
                continue
            if inp.lower() == "reset":
                confirm = input("  Delete ALL data for ALL patients? (yes/no): ").strip()
                if confirm.lower() == "yes":
                    db.close()
                    import shutil
                    shutil.rmtree(DB_DIR, ignore_errors=True)
                    print("  ✅ All data deleted. Restart the program.")
                    break
                else:
                    print("  Cancelled.")
                continue
            if inp.lower() == "reset patient":
                target = input("  Enter Patient ID to delete: ").strip()
                if not target:
                    print("  Cancelled.")
                    continue
                confirm = input(f"  Delete all data for {target}? (yes/no): ").strip()
                if confirm.lower() == "yes":
                    db.conn.execute("DELETE FROM avoidance_patterns WHERE patient_id=?", (target,))
                    db.conn.execute("DELETE FROM clinical_observations WHERE patient_id=?", (target,))
                    db.conn.execute("DELETE FROM session_data WHERE patient_id=?", (target,))
                    db.conn.execute("DELETE FROM patients WHERE patient_id=?", (target,))
                    db.conn.commit()
                    print(f"  ✅ Patient {target} deleted.")
                else:
                    print("  Cancelled.")
                continue
            print("  Unknown command. Try: reset, reset patient, db, quit")
        db.close()
        import sys
        sys.exit(0)

    # Normal patient mode
    print("'quit' to exit, 'state' to inspect, 'db' to view DB.\n")

    result = start_session(app, db, pid)
    _print_step(result)
    # _print_state(result)
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
        if inp.lower() == "state":
            v = app.get_state({"configurable": {
                "thread_id": f"patient_{pid}_s0"}}).values
            _print_state(v)
            continue
        if inp.lower() == "db":
            db.print_patient_summary(pid)
            continue
        if inp.lower() == "help":
            print("\n  Commands:")
            print("    state         — show current WETState")
            print("    db            — show patient data from database")
            print("    quit          — exit")
            print()
            continue
        print()
        result = run_turn(app, pid, inp)
        _print_step(result)
        # _print_state(result)
        print(f"\nTHERAPIST:\n{get_ai_msg(result)}\n")

        if result.get("current_step") == "safety_stop":
            print("=" * 60)
            print(f"  ⚠️  SESSION PAUSED — Risk level: {result.get('safety_risk', 'UNKNOWN')}")
            print("  Patient is being referred to a human clinician.")
            print("=" * 60)
            break

        if result.get("session_complete"):
            print("=" * 60)
            print("  SESSION 0 COMPLETE — Data saved to database")
            print("=" * 60)
            db.print_patient_summary(pid)
            break

    db.close()