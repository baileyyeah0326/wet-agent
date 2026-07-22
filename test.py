"""
Automated Integration Test — Session 0 → Session 1

Runs the full therapy flow programmatically without Streamlit.
Simulates a patient (Sarah, car accident) and verifies data extraction.

Usage:
    python test_integration.py
"""

import sys, os, shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from session0 import create_app, start_session, run_turn, get_ai_msg, STEP_LABELS
from session1 import (
    create_app_s1, start_session1, run_turn_s1,
    get_ai_msg as get_ai_msg_s1, STEP_LABELS_S1,
)

PID = "TEST_AUTO"
DATA_DIR = Path(__file__).parent / "data"

S0_RESPONSES = [
    "Hi. I'm Sarah. I'm pretty nervous but my doctor said this could help.",
    "I was in a car accident about a year and a half ago. A drunk driver ran a red light and hit my car. My daughter was in the back seat. She's okay physically, but I haven't been the same since. My doctor diagnosed me with PTSD.",
    "Yeah, it's been really hard. I'm glad I'm finally doing something about it.",
    "Honestly, I'm scared. But I'm also tired of feeling this way every day.",
    "I think I'm ready to try.",
    "Yes, definitely. My heart races at intersections, my hands get sweaty, and I grip the steering wheel so hard my knuckles turn white.",
    "I didn't realize those were all connected. Makes sense.",
    "I have flashbacks where I hear the crash. And I smell something burning. It comes out of nowhere.",
    "It's a relief to know my brain isn't broken.",
    "I stopped driving completely. I avoid that intersection. And I won't let my daughter ride with anyone else.",
    "So by avoiding everything I'm making it worse? Frustrating but it makes sense.",
    "Nightmares almost every night. And I'm so irritable with my family.",
    "No, that covers it.",
    "Writing about it scares me. But I'll do it if it helps me be a better mom.",
    "Yes, I'm ready.",
    "It feels good to talk about it. Nobody really asks how I'm doing.",
    "I can't drive, can't sleep, snap at my family. My daughter asked why Mommy is always sad.",
    "I want to drive again. I want to sleep without nightmares. And I want to stop being so angry with my family.",
    "How many sessions is this?",
    "Okay, makes sense. I'm ready.",
    "The beginning was seeing the headlights coming at us through the red light.",
    "It ended when the paramedics told me my daughter was okay.",
]

S1_RESPONSES = [
    "I almost didn't come today. I've been dreading writing about it.",
    "Okay, write with detail including feelings. Got it.",
    "Yes, that still feels right. Headlights and then paramedics saying she's okay.",
    "Write about what I saw, heard, smelled, and what I was thinking and feeling?",
    "Got it.",
    "What if I can't write for the full 30 minutes?",
    "Okay, I'll try.",
    "Makes sense. Like a thermometer for anxiety.",
    "Right now I'd say about 65.",
    "I saw the headlights first. Two bright white lights coming from the left through the red light. Time slowed down. I thought 'he's not stopping' and 'oh god Emma is in the back seat.' The sound was horrible — crunching metal and glass. I could smell something burning. Emma was screaming. I couldn't turn around. I kept screaming her name. I thought she was dying. I thought I killed my daughter. The door was crushed against my leg. Then the paramedics came. When they said Emma was okay I finally cried. I couldn't stop shaking. The guilt — I still feel it every day.",
    "About 80. That was really hard.",
    "Harder than I expected. I remembered things I didn't think I remembered.",
]


def get_step(result):
    return result.get("current_step", "").replace("_done", "")


def print_turn(turn, result, patient_msg=None, labels=STEP_LABELS):
    step = get_step(result)
    label = labels.get(step, STEP_LABELS_S1.get(step, step))
    ai = ""
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and not isinstance(msg, type(None)):
            from langchain_core.messages import AIMessage
            if isinstance(msg, AIMessage):
                ai = msg.content
                break
    ai_short = ai[:150] + "..." if len(ai) > 150 else ai
    print(f"  [{turn:2d}] {label}")
    print(f"       AI: {ai_short}")
    if patient_msg:
        p_short = patient_msg[:100] + "..." if len(patient_msg) > 100 else patient_msg
        print(f"       PT: {p_short}")


def run_session(app, pid, responses, run_fn, get_msg_fn, label, start_fn, labels):
    print(f"\n{'═'*60}")
    print(f"  {label}")
    print(f"{'═'*60}")

    result = start_fn(app)
    print_turn(0, result, labels=labels)

    turn = 0
    idx = 0
    max_turns = len(responses) + 20  # safety limit

    while idx < len(responses) and not result.get("session_complete") and turn < max_turns:
        patient_msg = responses[idx]
        idx += 1
        turn += 1
        result = run_fn(app, pid, patient_msg)
        print_turn(turn, result, patient_msg, labels)

        if result.get("current_step") == "safety_stop":
            print("\n  ⚠️  SAFETY STOP")
            break

    if result.get("session_complete"):
        print(f"\n  ✅ {label} COMPLETE ({turn} turns, {idx}/{len(responses)} responses used)")
    elif turn >= max_turns:
        print(f"\n  ❌ {label} HIT MAX TURNS ({max_turns})")
    else:
        print(f"\n  ⚠️  {label} — ran out of responses ({idx}/{len(responses)})")

    return result


def verify_s0(db, pid):
    print(f"\n{'─'*60}")
    print("  S0 VERIFICATION")
    print(f"{'─'*60}")
    p = db.get_patient(pid)
    checks = []

    def check(name, ok):
        checks.append(ok)
        print(f"  {'✅' if ok else '❌'} {name}")

    check("Patient exists", p is not None)
    if not p:
        return False
    check("trauma_described = True", p.get("trauma_described") == True)
    check("index_trauma not empty", bool(p.get("index_trauma")))
    check("reason_for_therapy not empty", bool(p.get("reason_for_therapy")))
    check("therapy_goals >= 1", len(p.get("therapy_goals", [])) >= 1)
    check("bookends.beginning exists", bool(p.get("trauma_bookends", {}).get("beginning")))
    check("bookends.end exists", bool(p.get("trauma_bookends", {}).get("end")))
    check("current_session == 1", p.get("current_session") == 1)

    av = db.get_avoidance_patterns(pid)
    check("avoidance_patterns >= 1", len(av) >= 1)

    obs = db.get_observations(pid, session_num=0)
    check("observations >= 1", len(obs) >= 1)

    print(f"\n  Goals: {p.get('therapy_goals', [])}")
    print(f"  Bookends: {p.get('trauma_bookends', {})}")
    print(f"  Avoidance: {len(av)} patterns")
    print(f"  Observations: {len(obs)}")

    return all(checks)


def verify_s1(db, pid):
    print(f"\n{'─'*60}")
    print("  S1 VERIFICATION")
    print(f"{'─'*60}")
    p = db.get_patient(pid)
    sessions = db.get_sessions(pid)
    s1 = [s for s in sessions if s.get("session_num") == 1]
    checks = []

    def check(name, ok):
        checks.append(ok)
        print(f"  {'✅' if ok else '❌'} {name}")

    check("current_session == 2", p.get("current_session") == 2 if p else False)
    check("Session 1 data exists", len(s1) >= 1)

    if s1:
        d = s1[-1]
        check("suds_pre recorded", d.get("suds_pre") is not None)
        check("suds_post recorded", d.get("suds_post") is not None)
        check("narrative recorded", bool(d.get("narrative")))
        check("session_summary recorded", bool(d.get("session_summary")))
        print(f"\n  SUDs: {d.get('suds_pre')} → {d.get('suds_post')}")
        n = d.get("narrative", "")
        print(f"  Narrative: {n[:100]}..." if n else "  Narrative: None")

    obs = db.get_observations(pid, session_num=1)
    check("S1 observations >= 1", len(obs) >= 1)

    return all(checks)


if __name__ == "__main__":
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    print("  Cleaned test data.\n")

    # Session 0
    app_s0, db = create_app()
    result_s0 = run_session(
        app_s0, PID, S0_RESPONSES, run_turn, get_ai_msg,
        "SESSION 0", lambda app: start_session(app, db, PID), STEP_LABELS)
    s0_ok = verify_s0(db, PID)

    # Session 1
    s1_ok = False
    if s0_ok:
        app_s1, _ = create_app_s1()
        result_s1 = run_session(
            app_s1, PID, S1_RESPONSES, run_turn_s1, get_ai_msg_s1,
            "SESSION 1", lambda app: start_session1(app, db, PID), STEP_LABELS_S1)
        s1_ok = verify_s1(db, PID)
    else:
        print("\n  ⚠️  S0 failed — skipping S1")

    print(f"\n{'═'*60}")
    print(f"  Session 0: {'✅ PASS' if s0_ok else '❌ FAIL'}")
    print(f"  Session 1: {'✅ PASS' if s1_ok else '❌ FAIL'}")
    print(f"{'═'*60}\n")
    db.close()