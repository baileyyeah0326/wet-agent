# Step 4 — Review Bookends

## Prompt Task
Review the trauma bookends from Session 0 with the patient.

The bookends (beginning and end of the trauma memory) should be
available in the context from Session 0. Reference them directly:

"Before you start writing, let's go over the bookends again —
the beginning and the end of the memory. Last time, you told me
the beginning was [beginning from S0] and the end was [end from S0].
Does that still feel right, or has anything shifted?"

If bookends are NOT in context (data missing), ask the patient
to remind you:
"Before you start writing, let's review the bookends — the
beginning and the end of the memory you'll write about.
Can you remind me where the memory starts and where it ends?"

2-3 sentences.

## Judge Criteria
pass=true when:
1. The beginning and end bookends are confirmed or updated
2. Patient agreed they are ready to use these bookends

If the patient wants to change a bookend, accept the change and
extract the updated values.

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
field: beginning | type: string | description: beginning of trauma memory (confirmed or updated)
field: end | type: string | description: end of trauma memory (confirmed or updated)
observation: bookends_review

## Clinical Notes
- Bookends may shift between sessions — this is normal
- If the patient changes a bookend, do NOT question it
- The end should still be a point of safety, not the climax
- Keep this step brief — confirm and move on
