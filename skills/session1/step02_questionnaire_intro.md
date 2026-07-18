# Step 2 — Questionnaire Introduction

## Prompt Task
Introduce the pre-session questionnaires to the patient.

Deliver conversationally:
"Before we begin today's session, I'd like to introduce something
we'll be doing at the start of each session. You'll be asked to
complete a few brief questionnaires about your symptoms and how
you've been feeling since our last meeting. These questionnaires
usually take just a few minutes to complete. Their purpose is to
help us track your progress over time. They give us an objective
way to see how your symptoms are changing, identify areas that
are improving, and notice if there are any concerns that we
should pay closer attention to. There are no right or wrong
answers. The most important thing is to answer each question as
honestly as you can based on your experiences over the past week
or two. Do you have any questions before we get started?"

## Judge Criteria
pass=true when:
1. The patient has been told about the questionnaires
2. If the patient had questions, they have been answered
3. The patient is ready to proceed

"No questions" or "Let's start" or "Okay" → pass.
If the patient asks a question → answer it, then ask if ready → pass on confirmation.

## Follow-up Guidance
If the patient asks a question about the questionnaires, answer
briefly and warmly. Common questions:
- "How long does it take?" → "Just a few minutes each."
- "Why do I have to do this?" → "It helps us track your progress."
- "Will you see my answers?" → "Yes, we review them together when relevant."
After answering, ask "Ready to get started?"

## Data to Extract
None

## Clinical Notes
- Keep this brief — 1-2 turns max
- The questionnaires are PCL-5 (PTSD symptoms) and PHQ-9 (depression)
- Don't over-explain — just introduce and check for questions
