"""
Standardized Questionnaires — PCL-5 and PHQ-9

Administered before Sessions 1-5 to track symptom changes.
Renders as Streamlit forms, stores scores in PatientDB.
"""

import streamlit as st

# ═══════════════════════════════════════════════════════════════════
# PCL-5 — PTSD Checklist for DSM-5 (20 items, 0-4 scale)
# ═══════════════════════════════════════════════════════════════════

PCL5_INSTRUCTIONS = (
    "Below is a list of problems that people sometimes have in response "
    "to a very stressful experience. Keeping your worst event in mind, "
    "please read each problem carefully and then select one of the numbers "
    "to indicate how much you have been bothered by that problem "
    "**in the past month**."
)

PCL5_SCALE = {
    0: "Not at all",
    1: "A little bit",
    2: "Moderately",
    3: "Quite a bit",
    4: "Extremely",
}

PCL5_ITEMS = [
    "Repeated, disturbing, and unwanted memories of the stressful experience?",
    "Repeated, disturbing dreams of the stressful experience?",
    "Suddenly feeling or acting as if the stressful experience were actually happening again (as if you were actually back there reliving it)?",
    "Feeling very upset when something reminded you of the stressful experience?",
    "Having strong physical reactions when something reminded you of the stressful experience (for example, heart pounding, trouble breathing, sweating)?",
    "Avoiding memories, thoughts, or feelings related to the stressful experience?",
    "Avoiding external reminders of the stressful experience (for example, people, places, conversations, activities, objects, or situations)?",
    "Trouble remembering important parts of the stressful experience?",
    "Having strong negative beliefs about yourself, other people, or the world (for example, having thoughts such as: I am bad, there is something seriously wrong with me, no one can be trusted, the world is completely dangerous)?",
    "Blaming yourself or someone else for the stressful experience or what happened after it?",
    "Having strong negative feelings such as fear, horror, anger, guilt, or shame?",
    "Loss of interest in activities that you used to enjoy?",
    "Feeling distant or cut off from other people?",
    "Trouble experiencing positive feelings (for example, being unable to feel happiness or have loving feelings for people close to you)?",
    "Irritable behavior, angry outbursts, or acting aggressively?",
    "Taking too many risks or doing things that could cause you harm?",
    'Being "superalert" or watchful or on guard?',
    "Feeling jumpy or easily startled?",
    "Having difficulty concentrating?",
    "Trouble falling or staying asleep?",
]


# ═══════════════════════════════════════════════════════════════════
# PHQ-9 — Patient Health Questionnaire (9 items, 0-3 scale)
# ═══════════════════════════════════════════════════════════════════

PHQ9_INSTRUCTIONS = (
    "Over the **last 2 weeks**, how often have you been bothered "
    "by any of the following problems?"
)

PHQ9_SCALE = {
    0: "Not at all",
    1: "Several days",
    2: "More than half the days",
    3: "Nearly every day",
}

PHQ9_ITEMS = [
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading the newspaper or watching television",
    "Moving or speaking so slowly that other people could have noticed? Or the opposite — being so fidgety or restless that you have been moving around a lot more than usual",
    "Thoughts that you would be better off dead or of hurting yourself in some way",
]

PHQ9_DIFFICULTY = (
    "If you checked off any problems, how difficult have these problems "
    "made it for you to do your work, take care of things at home, or "
    "get along with other people?"
)

PHQ9_DIFFICULTY_OPTIONS = [
    "Not difficult at all",
    "Somewhat difficult",
    "Very difficult",
    "Extremely difficult",
]


# ═══════════════════════════════════════════════════════════════════
# Streamlit Rendering
# ═══════════════════════════════════════════════════════════════════

def render_questionnaires(session_num: int) -> dict | None:
    """Render PCL-5 and PHQ-9 as Streamlit forms.

    Returns:
        dict with scores if submitted, None if not yet submitted.
        {"pcl5_scores": [int x20], "pcl5_total": int,
         "phq9_scores": [int x9], "phq9_total": int,
         "phq9_difficulty": str}
    """
    st.subheader(f"📋 Pre-Session Questionnaires (Session {session_num})")
    st.markdown(
        "Please complete both questionnaires before we begin today's session."
    )

    with st.form("questionnaire_form"):
        # ── PCL-5 ──
        st.markdown("---")
        st.markdown("### PCL-5 — PTSD Checklist")
        st.markdown(PCL5_INSTRUCTIONS)

        pcl5_responses = []
        for i, item in enumerate(PCL5_ITEMS):
            st.markdown(f"**{i+1}.** {item}")
            val = st.radio(
                f"pcl5_{i+1}",
                options=[0, 1, 2, 3, 4],
                format_func=lambda x: f"{x} — {PCL5_SCALE[x]}",
                horizontal=True,
                key=f"pcl5_q{i+1}_s{session_num}",
                label_visibility="collapsed",
            )
            pcl5_responses.append(val)

        # ── PHQ-9 ──
        st.markdown("---")
        st.markdown("### PHQ-9 — Patient Health Questionnaire")
        st.markdown(PHQ9_INSTRUCTIONS)

        phq9_responses = []
        for i, item in enumerate(PHQ9_ITEMS):
            st.markdown(f"**{i+1}.** {item}")
            val = st.radio(
                f"phq9_{i+1}",
                options=[0, 1, 2, 3],
                format_func=lambda x: f"{x} — {PHQ9_SCALE[x]}",
                horizontal=True,
                key=f"phq9_q{i+1}_s{session_num}",
                label_visibility="collapsed",
            )
            phq9_responses.append(val)

        # Difficulty question
        st.markdown("---")
        st.markdown(PHQ9_DIFFICULTY)
        difficulty = st.radio(
            "Difficulty level",
            options=PHQ9_DIFFICULTY_OPTIONS,
            key=f"phq9_diff_s{session_num}",
            label_visibility="collapsed",
        )

        # Submit
        st.markdown("---")
        submitted = st.form_submit_button(
            "✅ Submit Questionnaires",
            use_container_width=True,
        )

        if submitted:
            pcl5_total = sum(pcl5_responses)
            phq9_total = sum(phq9_responses)

            return {
                "pcl5_scores": pcl5_responses,
                "pcl5_total": pcl5_total,
                "phq9_scores": phq9_responses,
                "phq9_total": phq9_total,
                "phq9_difficulty": difficulty,
            }

    return None


def display_scores_summary(scores: dict):
    """Display a summary of questionnaire scores."""
    col1, col2 = st.columns(2)
    with col1:
        pcl5_total = scores["pcl5_total"]
        st.metric("PCL-5 Total", f"{pcl5_total} / 80")
        if pcl5_total >= 31:
            st.warning("Above clinical threshold (≥31)")
        else:
            st.success("Below clinical threshold")
    with col2:
        phq9_total = scores["phq9_total"]
        st.metric("PHQ-9 Total", f"{phq9_total} / 27")
        if phq9_total >= 10:
            severity = "Moderate" if phq9_total < 15 else (
                "Moderately severe" if phq9_total < 20 else "Severe")
            st.warning(f"Depression severity: {severity}")
        elif phq9_total >= 5:
            st.info("Mild depression")
        else:
            st.success("Minimal depression")
