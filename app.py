"""
WET Agent — Session 0 (Streamlit Web UI)
"""

import streamlit as st
import time
from session0 import (
    create_app, start_session, run_turn, get_ai_msg,
    STEP_LABELS,
)
from patient_db import DB_BACKEND

st.set_page_config(
    page_title="WET Therapy — Session 0",
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

# ── Session state init ──
if "app" not in st.session_state:
    app, db = create_app()
    st.session_state.app = app
    st.session_state.db = db
    st.session_state.pid = None
    st.session_state.started = False
    st.session_state.chat_history = []
    st.session_state.session_ended = False
    st.session_state.end_reason = None
    st.session_state.admin_mode = False
    st.session_state.pending_input = None


def get_step_label(result):
    step = result.get("current_step", "")
    base = step.replace("_done", "")
    return STEP_LABELS.get(base, step)


def reset_to_login():
    st.session_state.started = False
    st.session_state.chat_history = []
    st.session_state.session_ended = False
    st.session_state.end_reason = None
    st.session_state.pid = None
    st.session_state.admin_mode = False
    st.session_state.pending_input = None


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


def rebuild_chat_from_messages(result):
    from langchain_core.messages import AIMessage, HumanMessage
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage):
            label = msg.additional_kwargs.get("step_label", "")
            st.session_state.chat_history.append(
                ("therapist", msg.content, label))
        elif isinstance(msg, HumanMessage):
            st.session_state.chat_history.append(
                ("patient", msg.content, ""))


# ══════════════════════════════════════════════════════
# Admin Panel
# ══════════════════════════════════════════════════════
if st.session_state.admin_mode:
    st.title("🔧 Admin Panel")

    if st.button("← Back to Login"):
        st.session_state.admin_mode = False
        st.rerun()

    st.markdown("---")

    # View Patient
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
                avoidance = st.session_state.db.get_avoidance_patterns(view_pid.strip())
                if avoidance:
                    st.markdown("**Avoidance Patterns:**")
                    for a in avoidance:
                        st.markdown(f"- {a['pattern']}")
            else:
                st.warning(f"Patient '{view_pid}' not found.")

    st.markdown("---")

    # Reset Patient
    st.subheader("🗑️ Reset Patient")
    reset_pid = st.text_input("Patient ID to reset:", key="admin_reset")
    if st.button("Delete Patient Data"):
        if reset_pid:
            pid_clean = reset_pid.strip()
            try:
                cur = st.session_state.db.conn.cursor()
                for table in ["avoidance_patterns", "clinical_observations",
                              "session_data", "patients"]:
                    cur.execute(
                        st.session_state.db._q(
                            f"DELETE FROM {table} WHERE patient_id = ?"),
                        (pid_clean,))
                if DB_BACKEND != "postgres":
                    st.session_state.db.conn.commit()
                st.success(f"✅ Patient '{pid_clean}' deleted.")
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")

    # Reset All
    st.subheader("⚠️ Reset All Data")
    st.warning("This will delete ALL patients and ALL session data permanently.")
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


# ══════════════════════════════════════════════════════
# Login Screen
# ══════════════════════════════════════════════════════
if not st.session_state.started:
    st.title("🧠 WET Therapy — Session 0")
    st.markdown(
        "Welcome. This is the pre-treatment assessment session for "
        "Written Exposure Therapy (WET)."
    )

    with st.form("login_form"):
        pid = st.text_input("Enter Patient ID:", placeholder="e.g. P001")
        start_clicked = st.form_submit_button("Start Session")

    if st.button("🔧 Admin Panel"):
        st.session_state.admin_mode = True
        st.rerun()

    if start_clicked:
        if not pid or not pid.strip():
            st.error("Please enter a Patient ID.")
            st.stop()

        st.session_state.pid = pid.strip()

        try:
            with st.spinner("Starting session..."):
                result = start_session(
                    st.session_state.app,
                    st.session_state.db,
                    st.session_state.pid)
        except Exception as e:
            st.error(f"Error starting session: {str(e)[:200]}")
            st.stop()

        if result.get("session_complete"):
            rebuild_chat_from_messages(result)
            st.session_state.session_ended = True
            st.session_state.end_reason = "complete"
            st.session_state.started = True
        else:
            rebuild_chat_from_messages(result)
            st.session_state.started = True

        st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════
# Session Ended Screen
# ══════════════════════════════════════════════════════
if st.session_state.session_ended:
    st.title("🧠 WET Therapy — Session 0")

    display_chat_history()

    if st.session_state.end_reason == "safety":
        st.error("⚠️ Session paused — patient referred to human clinician.")
    else:
        st.success("✅ Session 0 complete — data saved.")

    with st.expander("📋 Patient Record"):
        p = st.session_state.db.get_patient(st.session_state.pid)
        if p:
            st.json(p)

    if st.button("🔄 New Patient"):
        reset_to_login()
        st.rerun()

    st.stop()


# ══════════════════════════════════════════════════════
# Active Session
# ══════════════════════════════════════════════════════
st.title("🧠 WET Therapy — Session 0")
st.caption(f"Patient: {st.session_state.pid}")

# Display all previous messages
display_chat_history()

# Phase 2: Process pending input (patient message already visible)
if st.session_state.pending_input:
    user_input = st.session_state.pending_input
    st.session_state.pending_input = None

    try:
        with st.spinner("Therapist is thinking..."):
            result = run_turn(
                st.session_state.app,
                st.session_state.pid,
                user_input)
    except Exception as e:
        st.error(f"An error occurred: {str(e)[:200]}. Please try again.")
        st.stop()

    ai_msg = get_ai_msg(result)
    label = get_step_label(result)

    if result.get("current_step") == "safety_stop":
        st.markdown(f'<div class="step-label">⚠️ Safety</div>', unsafe_allow_html=True)
        fake_stream(ai_msg, "safety-msg")
        st.session_state.chat_history.append(("safety", ai_msg, "⚠️ Safety"))
        st.session_state.session_ended = True
        st.session_state.end_reason = "safety"
        time.sleep(1)
        st.rerun()

    elif result.get("session_complete"):
        st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
        fake_stream(ai_msg)
        st.session_state.chat_history.append(("therapist", ai_msg, label))
        st.session_state.session_ended = True
        st.session_state.end_reason = "complete"
        time.sleep(1)
        st.rerun()

    else:
        st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
        fake_stream(ai_msg)
        st.session_state.chat_history.append(("therapist", ai_msg, label))

    st.rerun()

# Chat input
user_input = st.chat_input("Type your response...")

if user_input:
    # Phase 1: Show patient message immediately
    st.session_state.chat_history.append(("patient", user_input, ""))
    st.session_state.pending_input = user_input
    st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("### Tools")

    if st.button("📊 View State"):
        state = st.session_state.app.get_state({"configurable": {
            "thread_id": f"patient_{st.session_state.pid}_s0"}}).values
        st.json({
            "current_step": state.get("current_step", ""),
            "reason_for_therapy": state.get("reason_for_therapy", ""),
            "trauma_described": state.get("trauma_described", False),
            "index_trauma": state.get("index_trauma", ""),
            "therapy_goals": state.get("therapy_goals", []),
            "trauma_bookends": state.get("trauma_bookends", {}),
            "avoidance_patterns": [a.get("pattern", "")
                for a in state.get("avoidance_patterns", [])],
            "session_complete": state.get("session_complete", False),
        })

    if st.button("📋 View DB"):
        p = st.session_state.db.get_patient(st.session_state.pid)
        if p:
            st.json(p)
        else:
            st.warning("Patient not found in DB.")

    st.markdown("---")

    if st.button("🚪 End Session"):
        reset_to_login()
        st.rerun()