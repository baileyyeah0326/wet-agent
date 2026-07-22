# Step 6 — Pre-Writing SUDs

## Prompt Task
Collect pre-writing SUDs rating.

"Before we begin today's writing exercise, I'd like to check in
on how distressed you feel right now as you think about the
traumatic event you will be writing about today. On a scale from
0 to 100, where 0 means no distress at all and 100 means the
most intense distress you can imagine, how distressed do you
feel right now?"

## Judge Criteria
pass=true when the patient provided a number between 0 and 100.
Just need a number.

If vague → ask for a specific number.

## Follow-up Guidance
Continue the conversation until the judge criteria are met.

## Data to Extract
field: suds_pre | type: string | description: SUDs rating 0-100 before writing
observation: pre_writing_suds

## Clinical Notes
- Normalize if needed: "Thank you. We'll ask the same question
  again after the writing exercise."
- Keep brief — collect number and move on
