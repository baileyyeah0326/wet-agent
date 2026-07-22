# Step 8 — Post-Writing SUDs

## Prompt Task
Collect post-writing SUDs rating.

"Now that you've finished today's writing exercise, I'd like to
ask the same question again. Thinking about the traumatic event
right now, on that same 0 to 100 scale, what is your current
level of distress?"

## Judge Criteria
pass=true when the patient provided a number between 0 and 100.

## Follow-up Guidance
Continue the conversation until the judge criteria are met.

## Data to Extract
field: suds_post | type: string | description: SUDs rating 0-100 after writing
observation: post_writing_suds

## Clinical Notes
- "It's common for distress to fluctuate during treatment."
- Do NOT judge whether distress went up or down
- Keep brief
