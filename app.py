"""
WET Agent — Session 0 (Streamlit Web UI)

Run locally:  streamlit run app.py
Deploy:       Push to GitHub → connect Streamlit Cloud
"""

import streamlit as st
from session0 import (
    create_app, start_session, run_turn, get_ai_msg,
    STEP_LABELS, _print_state,
)
from patient_db import DB_BACKEND

# ── Page config ──
st.set_page_config(
    page_title="WET Therapy — Session 0",
    page_icon="🧠",
    layout="centered",
)

# ── Custom CSS ──
st.markdown("""
<style>
    .stApp {
        max-width: 800px;
        margin: 0 auto;
    }
    .therapist-msg {
        background-color: #f0f7f4;
        border-left: 4px solid #2e7d5b;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .patient-msg {
        background-color: #f0f0f8;
        border-left: 4px solid #5b5ba0;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .safety-msg {
        background-color: #fef0f0;
        border-left: 4px solid #c0392b;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 8px 0;
    }
    .step-label {
        font-size: 0.85em;
        color: #888;
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state init ──
if "app" not in st.session_state:
    app, db = create_app()
    st.session_state.app = app
    st.session_state.db = db
    st.session_state.pid = None
    st.session_state.started = False
    st.session_state.chat_history = []  # list of (role, message, step_label)
    st.session_state.session_ended = False
    st.session_state.end_reason = None  # "complete" or "safety"


def get_step_label(result):
    step = result.get("current_step", "")
    base = step.replace("_done", "")
    return STEP_LABELS.get(base, step)


# ── Login screen ──
if not st.session_state.started:
    st.title("🧠 WET Therapy — Session 0")
    st.markdown(
        "Welcome. This is the pre-treatment assessment session for "
        "Written Exposure Therapy (WET)."
    )

    pid = st.text_input("Enter Patient ID:", placeholder="e.g. P001 or 'admin'")

    col1, col2 = st.columns(2)
    with col1:
        start_clicked = st.button("Start Session", disabled=not pid)
    with col2:
        admin_clicked = st.button("🔧 Admin Panel")

    # ── Admin Panel ──
    if admin_clicked or (start_clicked and pid.strip().lower() == "admin"):
        st.markdown("---")
        st.subheader("🔧 Admin Panel")

        # View patient
        st.markdown("**View Patient Record**")
        view_pid = st.text_input("Patient ID to view:", key="admin_view")
        if st.button("📋 View Record", key="admin_view_btn"):
            if view_pid:
                p = st.session_state.db.get_patient(view_pid.strip())
                if p:
                    st.json(p)
                    obs = st.session_state.db.get_observations(view_pid.strip())
                    if obs:
                        st.markdown("**Observations:**")
                        for o in obs:
                            st.markdown(f"- [{o['obs_type']}] {o['content'][:200]}")
                else:
                    st.warning(f"Patient '{view_pid}' not found.")

        st.markdown("---")

        # Reset patient
        st.markdown("**Reset Patient**")
        reset_pid = st.text_input("Patient ID to reset:", key="admin_reset")
        if st.button("🗑️ Reset Patient", key="admin_reset_btn"):
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
                    st.success(f"Patient '{pid_clean}' deleted.")
                except Exception as e:
                    st.error(f"Error: {e}")

        st.stop()

    if start_clicked and pid.strip().lower() != "admin":
        st.session_state.pid = pid.strip()

        result = start_session(
            st.session_state.app,
            st.session_state.db,
            st.session_state.pid)

        if result.get("session_complete"):
            st.warning(f"Session 0 is already complete for {pid}.")
            st.session_state.session_ended = True
            st.session_state.end_reason = "complete"
            st.session_state.started = True
        else:
            ai_msg = get_ai_msg(result)
            label = get_step_label(result)
            st.session_state.chat_history.append(
                ("therapist", ai_msg, label))
            st.session_state.started = True

        st.rerun()

    st.stop()


# ── Session ended screen ──
if st.session_state.session_ended:
    st.title("🧠 WET Therapy — Session 0")

    # Show chat history
    for role, msg, label in st.session_state.chat_history:
        if role == "therapist":
            st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="therapist-msg">{msg}</div>', unsafe_allow_html=True)
        elif role == "safety":
            st.markdown(f'<div class="safety-msg">{msg}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="patient-msg">{msg}</div>', unsafe_allow_html=True)

    if st.session_state.end_reason == "safety":
        st.error("⚠️ Session paused — patient referred to human clinician.")
    else:
        st.success("✅ Session 0 complete — data saved.")

    # Show patient data
    with st.expander("📋 Patient Record"):
        p = st.session_state.db.get_patient(st.session_state.pid)
        if p:
            st.json(p)

    if st.button("🔄 New Patient"):
        st.session_state.started = False
        st.session_state.chat_history = []
        st.session_state.session_ended = False
        st.session_state.end_reason = None
        st.session_state.pid = None
        st.rerun()

    st.stop()


# ── Active session ──
st.title("🧠 WET Therapy — Session 0")
st.caption(f"Patient: {st.session_state.pid}")

# Show chat history
for role, msg, label in st.session_state.chat_history:
    if role == "therapist":
        st.markdown(f'<div class="step-label">{label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="therapist-msg">{msg}</div>', unsafe_allow_html=True)
    elif role == "safety":
        st.markdown(f'<div class="safety-msg">{msg}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="patient-msg">{msg}</div>', unsafe_allow_html=True)

# Input
user_input = st.chat_input("Type your response...")

if user_input:
    # Add patient message to history
    st.session_state.chat_history.append(("patient", user_input, ""))

    # Run turn
    result = run_turn(
        st.session_state.app,
        st.session_state.pid,
        user_input)

    ai_msg = get_ai_msg(result)
    label = get_step_label(result)

    # Check safety stop
    if result.get("current_step") == "safety_stop":
        st.session_state.chat_history.append(("safety", ai_msg, "⚠️ Safety"))
        st.session_state.session_ended = True
        st.session_state.end_reason = "safety"
    # Check session complete
    elif result.get("session_complete"):
        st.session_state.chat_history.append(("therapist", ai_msg, label))
        st.session_state.session_ended = True
        st.session_state.end_reason = "complete"
    else:
        st.session_state.chat_history.append(("therapist", ai_msg, label))

    st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("### Commands")
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
            "avoidance_patterns": [a.get("pattern", "") for a in state.get("avoidance_patterns", [])],
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
        st.session_state.started = False
        st.session_state.chat_history = []
        st.session_state.session_ended = False
        st.session_state.end_reason = None
        st.session_state.pid = None
        st.rerun()