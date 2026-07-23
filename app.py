"""
WET Agent — Streamlit Web UI (Multi-Session)
"""

import streamlit as st
import time

st.set_page_config(
    page_title="WET Therapy",
    page_icon="🧠",
    layout="centered",
)

st.markdown("""
<style>
    .stApp { max-width: 800px; margin: 0 auto; }
    .therapist-msg {
        background-color: #f0f7f4; border-left: 4px solid #2e7d5b;
        padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 8px 0;
    }
    .patient-msg {
        background-color: #f0f0f8; border-left: 4px solid #5b5ba0;
        padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 8px 0;
    }
    .safety-msg {
        background-color: #fef0f0; border-left: 4px solid #c0392b;
        padding: 12px 16px; border-radius: 0 8px 8px 0; margin: 8px 0;
    }
    .step-label { font-size: 0.85em; color: #888; margin-bottom: 4px; }
    .stTextInput div[data-testid="InputInstructions"] { display: none; }
</style>
""", unsafe_allow_html=True)

from session0 import (
    create_app as create_app_s0,
    start_session as start_session_s0,
    run_turn as run_turn_s0,
    get_ai_msg as get_ai_msg_s0,
    STEP_LABELS as STEP_LABELS_S0,
)
from session1 import (
    create_app_s1,
    start_session1,
    run_turn_s1,
    get_ai_msg,
    STEP_LABELS_S1,
)
from session2 import (
    create_app_s2,
    start_session2,
    run_turn_s2,
    get_ai_msg as get_ai_msg_s2,
    STEP_LABELS_S2,
)
from session3 import (
    create_app_s3,
    start_session3,
    run_turn_s3,
    get_ai_msg as get_ai_msg_s3,
    STEP_LABELS_S3,
)
from session4 import (
    create_app_s4,
    start_session4,
    run_turn_s4,
    get_ai_msg as get_ai_msg_s4,
    STEP_LABELS_S4,
)
from session5 import (
    create_app_s5,
    start_session5,
    run_turn_s5,
    get_ai_msg as get_ai_msg_s5,
    STEP_LABELS_S5,
)
from questionnaires import render_questionnaires, display_scores_summary
from patient_db import DB_BACKEND

# ═══════════════════════════════════════════════════════
# Session state init
# ═══════════════════════════════════════════════════════
if "initialized" not in st.session_state:
    app_s0, db = create_app_s0()
    app_s1, _ = create_app_s1()
    app_s2, _ = create_app_s2()
    app_s3, _ = create_app_s3()
    app_s4, _ = create_app_s4()
    app_s5, _ = create_app_s5()
    st.session_state.app_s0 = app_s0
    st.session_state.app_s1 = app_s1
    st.session_state.app_s2 = app_s2
    st.session_state.app_s3 = app_s3
    st.session_state.app_s4 = app_s4
    st.session_state.app_s5 = app_s5
    st.session_state.db = db
    st.session_state.pid = None
    st.session_state.page = "login"
    st.session_state.current_session_num = 0
    st.session_state.chat_history = []
    st.session_state.end_reason = None
    st.session_state.pending_input = None
    st.session_state.questionnaire_scores = None
    st.session_state.initialized = True


SESSION_NAMES = {
    0: "Session 0 — Pre-treatment",
    1: "Session 1 — First Writing",
    2: "Session 2 — Writing",
    3: "Session 3 — Writing",
    4: "Session 4 — Writing",
    5: "Session 5 — Final Writing",
}


def reset_to_login():
    st.session_state.pid = None
    st.session_state.page = "login"
    st.session_state.chat_history = []
    st.session_state.end_reason = None
    st.session_state.pending_input = None
    st.session_state.questionnaire_scores = None


def reset_to_progress():
    st.session_state.page = "progress"
    st.session_state.chat_history = []
    st.session_state.end_reason = None
    st.session_state.pending_input = None
    st.session_state.questionnaire_scores = None


def get_step_label(result, session_num):
    step = result.get("current_step", "")
    base = step.replace("_done", "")
    labels = STEP_LABELS_S0
    if session_num == 1:
        labels = STEP_LABELS_S1
    elif session_num == 2:
        labels = STEP_LABELS_S2
    elif session_num == 3:
        labels = STEP_LABELS_S3
    elif session_num == 4:
        labels = STEP_LABELS_S4
    elif session_num >= 5:
        labels = STEP_LABELS_S5
    return labels.get(base, step)


def display_chat_history():
    for role, msg, label in st.session_state.chat_history:
        if role == "therapist":
            st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="therapist-msg">{msg}</div>', unsafe_allow_html=True)
        elif role == "safety":
            st.markdown(f'<div class="safety-msg">{msg}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="patient-msg">{msg}</div>', unsafe_allow_html=True)


def fake_stream(text, css_class="therapist-msg"):
    placeholder = st.empty()
    displayed = ""
    for char in text:
        displayed += char
        placeholder.markdown(
            f'<div class="{css_class}">{displayed}▌</div>',
            unsafe_allow_html=True)
        time.sleep(0.015)
    placeholder.markdown(
        f'<div class="{css_class}">{displayed}</div>',
        unsafe_allow_html=True)


def rebuild_chat(result, session_num):
    from langchain_core.messages import AIMessage, HumanMessage
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage):
            label = msg.additional_kwargs.get("step_label", "")
            st.session_state.chat_history.append(("therapist", msg.content, label))
        elif isinstance(msg, HumanMessage):
            st.session_state.chat_history.append(("patient", msg.content, ""))


# ═══════════════════════════════════════════════════════
# PAGE: Admin Panel
# ═══════════════════════════════════════════════════════
if st.session_state.page == "admin":
    st.title("🔧 Admin Panel")

    if st.button("← Back to Login"):
        reset_to_login()
        st.rerun()

    st.markdown("---")

    st.subheader("📋 View Patient Record")
    view_pid = st.text_input("Patient ID to view:", key="admin_view")
    if st.button("View Record"):
        if view_pid:
            p = st.session_state.db.get_patient(view_pid.strip())
            if p:
                st.json(p)
                obs = st.session_state.db.get_observations(view_pid.strip())
                if obs:
                    st.markdown("**Observations:**")
                    for o in obs:
                        st.markdown(f"- **[{o['obs_type']}]** {o['content'][:300]}")
            else:
                st.warning(f"Patient '{view_pid}' not found.")

    st.markdown("---")

    st.subheader("🗑️ Reset Patient")
    reset_pid = st.text_input("Patient ID to reset:", key="admin_reset")
    if st.button("Delete Patient Data"):
        if reset_pid:
            try:
                cur = st.session_state.db.conn.cursor()
                for table in ["avoidance_patterns", "clinical_observations",
                              "session_data", "patients"]:
                    cur.execute(st.session_state.db._q(
                        f"DELETE FROM {table} WHERE patient_id = ?"),
                        (reset_pid.strip(),))
                if DB_BACKEND != "postgres":
                    st.session_state.db.conn.commit()
                st.success(f"✅ Patient '{reset_pid.strip()}' deleted.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    st.subheader("⚠️ Reset All Data")
    confirm = st.text_input("Type 'DELETE ALL' to confirm:", key="admin_reset_all")
    if st.button("🗑️ Delete Everything"):
        if confirm == "DELETE ALL":
            try:
                cur = st.session_state.db.conn.cursor()
                for table in ["avoidance_patterns", "clinical_observations",
                              "session_data", "patients"]:
                    cur.execute(f"DELETE FROM {table}")
                if DB_BACKEND != "postgres":
                    st.session_state.db.conn.commit()
                st.success("✅ All data deleted.")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Please type 'DELETE ALL' to confirm.")

    st.stop()


# ═══════════════════════════════════════════════════════
# PAGE: Login
# ═══════════════════════════════════════════════════════
if st.session_state.page == "login":
    st.title("🧠 Written Exposure Therapy")
    st.markdown("Welcome. Enter your Patient ID to continue.")

    with st.form("login_form"):
        pid = st.text_input("Patient ID:", placeholder="e.g. P001")
        start_clicked = st.form_submit_button("Continue")

    if st.button("🔧 Admin Panel"):
        st.session_state.page = "admin"
        st.rerun()

    if start_clicked:
        if not pid or not pid.strip():
            st.error("Please enter a Patient ID.")
            st.stop()
        st.session_state.pid = pid.strip()
        st.session_state.page = "progress"
        st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════
# PAGE: Progress
# ═══════════════════════════════════════════════════════
if st.session_state.page == "progress":
    st.title("🧠 Written Exposure Therapy")

    pid = st.session_state.pid
    patient = st.session_state.db.get_patient(pid)
    current_session = patient["current_session"] if patient else 0

    st.markdown(f"**Patient:** {pid}")
    st.markdown("---")

    st.subheader("📊 Treatment Progress")
    for i in range(6):
        name = SESSION_NAMES.get(i, f"Session {i}")
        if i < current_session:
            st.markdown(f"✅ **{name}** — Completed")
        elif i == current_session:
            st.markdown(f"▶ **{name}** — Ready")
        else:
            st.markdown(f"⬜ {name}")

    if current_session > 5:
        st.success("🎉 Treatment complete! All 6 sessions finished.")
        st.balloons()
        if st.button("← Back to Login"):
            reset_to_login()
            st.rerun()
        st.stop()

    st.markdown("---")

    sessions = st.session_state.db.get_sessions(pid)
    if sessions:
        pcl5_scores = [s["pcl5_score"] for s in sessions if s.get("pcl5_score") is not None]
        phq9_scores = [s["phq9_score"] for s in sessions if s.get("phq9_score") is not None]
        if pcl5_scores or phq9_scores:
            with st.expander("📈 Score Trajectory"):
                if pcl5_scores:
                    st.markdown(f"**PCL-5:** {pcl5_scores}")
                if phq9_scores:
                    st.markdown(f"**PHQ-9:** {phq9_scores}")

    session_name = SESSION_NAMES.get(current_session, f"Session {current_session}")

    if st.button(f"▶ Start {session_name}", use_container_width=True):
        st.session_state.current_session_num = current_session
        st.session_state.page = "session"
        st.rerun()

    st.markdown("---")
    if st.button("← Back to Login"):
        reset_to_login()
        st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════
# PAGE: Questionnaire (PCL-5 + PHQ-9)
# ═══════════════════════════════════════════════════════
if st.session_state.page == "questionnaire":
    session_num = st.session_state.current_session_num
    pid = st.session_state.pid

    # Check DB for existing scores (in case session_state was lost/expired)
    if not st.session_state.questionnaire_scores:
        try:
            existing_sessions = st.session_state.db.get_sessions(pid)
            for s in existing_sessions:
                if s.get("session_num") == session_num and s.get("pcl5_score") is not None:
                    st.session_state.questionnaire_scores = {
                        "pcl5_total": s["pcl5_score"],
                        "phq9_total": s.get("phq9_score", 0),
                    }
                    break
        except Exception:
            pass

    # Already submitted — show scores and continue button
    if st.session_state.questionnaire_scores:
        st.markdown("### Step 2/11 — Questionnaires Complete")
        st.success("✅ Questionnaires submitted!")
        display_scores_summary(st.session_state.questionnaire_scores)

        next_step = "Step 3" if session_num == 1 else "Step 2"
        if st.button(f"▶ Continue to {next_step}", use_container_width=True):
            # Add the saved Step 3 message to chat history
            if st.session_state.get("pending_step3_msg"):
                msg, label = st.session_state.pending_step3_msg
                st.session_state.chat_history.append(("therapist", msg, label))
                st.session_state.pending_step3_msg = None
            st.session_state.page = "session"
            st.rerun()

        st.stop()

    # Not yet submitted — show questionnaire form
    scores = render_questionnaires(session_num)

    if scores:
        pid = st.session_state.pid
        try:
            st.session_state.db.save_session(
                pid, session_num,
                pcl5_score=scores["pcl5_total"],
                phq9_score=scores["phq9_total"])
        except Exception:
            pass

        st.session_state.questionnaire_scores = scores
        st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════
# PAGE: Session Ended
# ═══════════════════════════════════════════════════════
if st.session_state.page == "ended":
    session_num = st.session_state.current_session_num
    session_name = SESSION_NAMES.get(session_num, f"Session {session_num}")
    st.title(f"🧠 {session_name}")

    display_chat_history()

    if st.session_state.end_reason == "safety":
        st.error("⚠️ Session paused — patient referred to human clinician.")
    else:
        st.success(f"✅ {session_name} complete — data saved.")

    with st.expander("📋 Patient Record"):
        p = st.session_state.db.get_patient(st.session_state.pid)
        if p:
            st.json(p)

    if st.button("🔄 Back to Progress", use_container_width=True):
        reset_to_progress()
        st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════
# PAGE: Active Session
# ═══════════════════════════════════════════════════════
if st.session_state.page == "session":
    session_num = st.session_state.current_session_num
    session_name = SESSION_NAMES.get(session_num, f"Session {session_num}")
    pid = st.session_state.pid

    # Start session if chat_history is empty
    if not st.session_state.chat_history:
        try:
            with st.spinner(f"Starting {session_name}..."):
                if session_num == 0:
                    result = start_session_s0(
                        st.session_state.app_s0,
                        st.session_state.db, pid)
                elif session_num == 1:
                    result = start_session1(
                        st.session_state.app_s1,
                        st.session_state.db, pid)
                elif session_num == 2:
                    result = start_session2(
                        st.session_state.app_s2,
                        st.session_state.db, pid)
                elif session_num == 3:
                    result = start_session3(
                        st.session_state.app_s3,
                        st.session_state.db, pid)
                elif session_num == 4:
                    result = start_session4(
                        st.session_state.app_s4,
                        st.session_state.db, pid)
                else:
                    result = start_session5(
                        st.session_state.app_s5,
                        st.session_state.db, pid)
        except Exception as e:
            st.error(f"Error: {str(e)[:200]}")
            st.stop()

        if result.get("session_complete"):
            rebuild_chat(result, session_num)
            st.session_state.page = "ended"
            st.session_state.end_reason = "complete"
            st.rerun()
        else:
            rebuild_chat(result, session_num)
            st.rerun()

    # Display
    st.title(f"🧠 {session_name}")
    st.caption(f"Patient: {pid}")

    display_chat_history()

    # Phase 2: Process pending input
    if st.session_state.pending_input:
        user_input = st.session_state.pending_input
        st.session_state.pending_input = None

        try:
            with st.spinner("Therapist is thinking..."):
                if session_num == 0:
                    result = run_turn_s0(
                        st.session_state.app_s0, pid, user_input)
                elif session_num == 1:
                    result = run_turn_s1(
                        st.session_state.app_s1, pid, user_input)
                elif session_num == 2:
                    result = run_turn_s2(
                        st.session_state.app_s2, pid, user_input)
                elif session_num == 3:
                    result = run_turn_s3(
                        st.session_state.app_s3, pid, user_input)
                elif session_num == 4:
                    result = run_turn_s4(
                        st.session_state.app_s4, pid, user_input)
                else:
                    result = run_turn_s5(
                        st.session_state.app_s5, pid, user_input)
        except Exception as e:
            st.error(f"An error occurred: {str(e)[:200]}. Please try again.")
            st.stop()

        if session_num == 0:
            ai_msg = get_ai_msg_s0(result)
        elif session_num == 1:
            ai_msg = get_ai_msg(result)
        elif session_num == 2:
            ai_msg = get_ai_msg_s2(result)
        elif session_num == 3:
            ai_msg = get_ai_msg_s3(result)
        elif session_num == 4:
            ai_msg = get_ai_msg_s4(result)
        else:
            ai_msg = get_ai_msg_s5(result)
        label = get_step_label(result, session_num)

        if result.get("current_step") == "safety_stop":
            st.markdown('<div class="step-label">⚠️ Safety</div>', unsafe_allow_html=True)
            fake_stream(ai_msg, "safety-msg")
            st.session_state.chat_history.append(("safety", ai_msg, "⚠️ Safety"))
            st.session_state.page = "ended"
            st.session_state.end_reason = "safety"
            time.sleep(1)
            st.rerun()

        elif result.get("session_complete"):
            st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
            fake_stream(ai_msg)
            st.session_state.chat_history.append(("therapist", ai_msg, label))
            st.session_state.page = "ended"
            st.session_state.end_reason = "complete"
            time.sleep(1)
            st.rerun()

        else:
            # Redirect to questionnaire form at the right moment
            current_step = result.get("current_step", "")
            needs_questionnaire = (
                session_num >= 1
                and not st.session_state.questionnaire_scores
                and (
                    # S1: after step2 (intro) passes → before step3
                    (session_num == 1 and current_step.startswith("s1_step3"))
                    # S2+: after step1 (welcome) passes → before step2 (discuss scores)
                    or (session_num >= 2 and current_step.startswith(f"s{session_num}_step2"))
                )
            )
            if needs_questionnaire:
                st.session_state.pending_step3_msg = (ai_msg, label)
                st.session_state.page = "questionnaire"
                st.rerun()

            st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
            fake_stream(ai_msg)
            st.session_state.chat_history.append(("therapist", ai_msg, label))

        st.rerun()

    # Chat input
    user_input = st.chat_input("Type your response...")

    if user_input:
        # Prevent duplicate submission
        last_patient_msg = ""
        for role, msg, _ in reversed(st.session_state.chat_history):
            if role == "patient":
                last_patient_msg = msg
                break
        if user_input == last_patient_msg:
            pass  # Skip duplicate
        else:
            st.session_state.chat_history.append(("patient", user_input, ""))
            st.session_state.pending_input = user_input
            st.rerun()

    # Sidebar
    with st.sidebar:
        st.markdown(f"### {session_name}")

        if st.button("📊 View State"):
            thread_id = f"patient_{pid}_s{session_num}"
            if session_num == 0:
                app = st.session_state.app_s0
            elif session_num == 1:
                app = st.session_state.app_s1
            elif session_num == 2:
                app = st.session_state.app_s2
            elif session_num == 3:
                app = st.session_state.app_s3
            elif session_num == 4:
                app = st.session_state.app_s4
            else:
                app = st.session_state.app_s5
            state = app.get_state({"configurable": {"thread_id": thread_id}}).values
            st.json({
                "current_step": state.get("current_step", ""),
                "session": session_num,
                "reason_for_therapy": state.get("reason_for_therapy", ""),
                "trauma_described": state.get("trauma_described", False),
                "index_trauma": state.get("index_trauma", ""),
                "therapy_goals": state.get("therapy_goals", []),
                "trauma_bookends": state.get("trauma_bookends", {}),
                "session_complete": state.get("session_complete", False),
            })

        if st.button("📋 View DB"):
            p = st.session_state.db.get_patient(pid)
            if p:
                st.json(p)
            sessions = st.session_state.db.get_sessions(pid)
            if sessions:
                st.markdown("**Session Data:**")
                for s in sessions:
                    st.markdown(f"Session {s.get('session_num')}:")
                    st.json({
                        "pcl5": s.get("pcl5_score"),
                        "phq9": s.get("phq9_score"),
                        "suds_pre": s.get("suds_pre"),
                        "suds_post": s.get("suds_post"),
                        "narrative": s.get("narrative", "")[:100] + "..." if s.get("narrative") else None,
                        "summary": s.get("session_summary", "")[:100] + "..." if s.get("session_summary") else None,
                    })

        st.markdown("---")

        if st.button("🚪 End Session"):
            reset_to_progress()
            st.rerun()