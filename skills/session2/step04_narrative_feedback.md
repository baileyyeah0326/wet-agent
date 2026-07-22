# Step 4 — Narrative Feedback

## Prompt Task
Provide feedback on the patient's previous writing session narrative.
The narrative from Session 1 should be available in context.

Evaluate and gently address:
1. Did they include thoughts and feelings, or just facts/details?
   - If mostly facts: "I noticed your writing focused a lot on
     what happened. Today, I'd also like you to include more
     about what you were thinking and feeling during the trauma."
2. Did they write about the index trauma, or a different event?
   - If different event: "I noticed you wrote about [X] last time.
     Today, let's focus on [the index trauma]."
3. Did they write enough? (brief vs detailed)
   - If very brief: "You did a great job starting. Today, try to
     add more detail — what you saw, heard, felt."

If the narrative was good (detailed, included emotions, focused):
"You did a really good job with your writing last time. You included
details and emotions, which is exactly what we're looking for."

Keep feedback brief, specific, and encouraging.

## Judge Criteria
pass=true when:
1. Feedback has been delivered
2. Patient acknowledged the feedback

"Okay" or "I'll try" → pass.

## Follow-up Guidance
Continue the conversation until the judge criteria are met.

## Data to Extract
observation: narrative_feedback

## Clinical Notes
- Be ENCOURAGING, not critical
- The feedback is about improving the NEXT writing, not grading the last one
- If narrative is not available in context, ask: "How did you feel
  about your writing last time? Was there anything you wanted to
  write about but didn't?"
- Common issues: avoidance (writing about something else), surface
  level (facts without emotions), too brief
