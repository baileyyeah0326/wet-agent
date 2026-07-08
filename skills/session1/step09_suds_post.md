# Step 9 — Post-Writing SUDs

## Prompt Task
Collect post-writing SUDs rating.

"Thank you for completing today's writing exercise. Before we talk
briefly about your experience, I'd like to ask you to rate your
current level of emotional distress using the same SUDS scale.

Remember: 0 means no distress at all, 100 means the highest level
of distress you can imagine.

Thinking about how you feel right now, what number best represents
your current level of distress?"

2-3 sentences.

## Judge Criteria
pass=true when:
1. Patient provided a number between 0 and 100

If vague or unsure: "There isn't a right or wrong answer. Just choose
the number that best reflects how distressed you feel right now."

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
field: suds_post | type: string | description: SUDs rating 0-100 after writing
observation: post_writing_suds

## Clinical Notes
- Do NOT comment on the comparison between pre and post SUDs
  unless clinically important
- If SUDs went UP: "It's completely normal to feel more activated
  after engaging with the memory."
- If SUDs went DOWN: brief acknowledgment, don't over-interpret
- Keep this brief — collect the number and move on
