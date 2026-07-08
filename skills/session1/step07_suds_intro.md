# Step 7 — Introduce SUDs + Pre-Writing SUDs

## Prompt Task
Introduce the SUDS concept and then collect pre-writing rating.

Deliver conversationally (NOT as a script):

1. "Before we begin today's writing, I'd like to introduce a simple
   way for us to monitor how you're feeling during treatment."

2. Explain the SUDS scale:
   - It stands for Subjective Units of Distress Scale
   - It's a way to rate how emotionally distressed you feel right now
   - Scale goes from 0 to 100:
     - 0 = completely calm, no distress at all
     - 100 = the most distressed you can imagine
   - No right or wrong answers — it's your personal rating

3. Explain how it will be used:
   - "I'll ask for your rating before writing, after writing,
     and sometimes a few minutes later"
   - "This helps us understand how your emotional responses change"

4. Normalize that distress may increase during writing:
   - "It's completely normal for distress to go up while writing.
     That doesn't mean something is wrong — it means you're
     engaging with the memory, which is part of the process."
   - "Over time, many people notice the intensity becomes more
     manageable."

5. Ask: "Do you have any questions about the SUDS scale?"

6. Then collect: "What is your current SUDS rating, from 0 to 100?"

## Judge Criteria
pass=true when:
1. SUDS concept has been explained
2. Patient provided a number between 0 and 100

If they give a vague answer ("pretty anxious"), ask for a specific number.
If they have questions about SUDS, answer them first, then ask for rating.

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
field: suds_pre | type: string | description: SUDs rating 0-100 before writing
observation: pre_writing_suds

## Clinical Notes
- This is the FIRST time the patient hears about SUDS
- Take time to explain it clearly — they'll use it every session
- If SUDs is high (70+), normalize: "That makes complete sense
  given what you're about to do"
- If very low (<10), note it (possible avoidance/numbing) but
  don't challenge
- After collecting the number, move on — don't dwell on it
