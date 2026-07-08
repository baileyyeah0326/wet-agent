# Step 7 — Writing Task (30 Minutes)

## Prompt Task
Tell the patient to begin writing now.

"Okay, it's time to start writing. Remember, write about the trauma
starting from the beginning, include sensory details, your thoughts,
and your feelings. You have 30 minutes. If you finish early, go back
to the beginning and write it again. Take your time, and begin
whenever you're ready."

After they submit their writing, acknowledge it briefly:
"Thank you for doing that. I know that wasn't easy."

## Judge Criteria
pass=true when:
1. Patient submitted their trauma narrative (any length)

The narrative should be about their trauma. If the patient writes
something completely unrelated or says "I can't do this":
- Validate their feelings
- Gently encourage: "Take your time. You can start with just
  one sentence about what happened."
- pass=false until they submit something related to the trauma

Do NOT judge the quality or detail of the writing. Any genuine
attempt counts.

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
field: narrative | type: string | description: the patient's trauma narrative text
observation: writing_task

## Clinical Notes
- This is the CORE therapeutic activity — treat it with gravity
- Do NOT comment on the content of the narrative
- Do NOT ask follow-up questions about the trauma details
- Simply acknowledge their effort: "Thank you for doing that"
- The narrative will be stored for clinical review
- In a real session this would be 30 minutes of handwriting;
  in the chat format the patient types their narrative
