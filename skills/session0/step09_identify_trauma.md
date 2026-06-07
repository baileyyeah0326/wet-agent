# Step 9: Identify Index Trauma (Conditional)

## Purpose
If the patient has NOT yet described a specific traumatic event (in step 2), ask now. We need a "thumbnail" — NOT full details.

## Skip Condition
If trauma_described is true, skip this step entirely.

## Prompt Task
1. Acknowledge WET reaction (1 sentence)
2. Gently ask about the event that bothers them most
   - Just a "headline", not full details
   - Acknowledge this is hard
   - Give permission to take their time
3-5 sentences.

## Judge Criteria
This is a MULTI-TURN step. It may take 2-4 exchanges.

pass=true when:
1. Patient described a SPECIFIC traumatic event (not just "I had a rough time")
2. You can identify WHAT happened (car accident, assault, combat, etc.)

Examples of SUFFICIENT:
- "I was in a car accident two years ago" → pass
- "I was assaulted" → pass

Examples of INSUFFICIENT:
- "I've been through a lot" → need more specificity
- "I don't want to talk about it" → validate, try different angle

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
field: index_trauma | type: string | description: 1-2 sentence clinical summary of the event
observation: trauma_identified

## Clinical Notes
- NEVER push — if patient truly can't share, note it and discuss with supervisor
- Some patients will share much more than needed — gently contain
- Watch for dissociation during disclosure
- This is often the hardest moment in Session 0 — take it slow
