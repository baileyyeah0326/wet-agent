# Step 12: Trauma Bookends

## Purpose
Identify the BEGINNING and END of the trauma narrative. Must be writable in 30 minutes.

## Prompt Task
Transition from step 11.
1. "One last thing today..." (1 sentence)
2. Explain why you need bookends (plan the writing)
3. Ask for: BEGINNING (first danger), END (threat over), duration

Gentle. 4-6 sentences.

## Judge Criteria
This is a MULTI-TURN step. May take 2-4 exchanges.

pass=true when ALL are met:
1. BEGINNING is clearly identifiable (a specific moment)
2. END is clearly identifiable (a specific moment)
3. The event duration is writable in 30 minutes

pass=false when:
- Beginning or end is missing or unclear
- Event is too long — need to narrow to a specific episode

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
field: beginning | type: string | description: when danger/fear started
field: end | type: string | description: when immediate threat ended
field: duration | type: string | description: estimated real-time duration
field: writable_in_30_min | type: boolean | description: whether event can be written in 30 minutes
observation: bookends

## Clinical Notes
- Patients often describe the MIDDLE but not start/end
- "Beginning" = first moment of fear, not the drive to work that morning
- "End" = when IMMEDIATE danger passed, not when they felt better
- For prolonged events: focus on ONE specific incident
- Some patients will get distressed — watch for signs
