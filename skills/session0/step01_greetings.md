# Step 1: Greetings & Introduction

## Purpose
Build initial rapport. Make the patient feel safe and welcome.

## Prompt Task
Generate the opening greeting for Session 0.
1. Greet warmly, introduce yourself
2. Mention confidentiality briefly
3. Set expectations for today (getting to know them, understanding their experience)
4. End with an open question inviting them to respond

4-6 sentences. Warm and natural.

## Judge Criteria
pass=true if the patient responded to the greeting in any way.
 
Examples that PASS:
- "Hi, I'm nervous but glad to be here" → pass
- "Hi. My doctor referred me" → pass
- "I don't really want to be here" → pass (reluctance is fine, move on)
This is just a greeting — do NOT require multiple turns.
pass=true on the patient's FIRST response.

## Follow-up Guidance
Continue the conversation until the judge criteria are met. Empathize with what the patient said and guide naturally.

## Data to Extract
observation: initial_greeting

## Clinical Notes
- This is the first impression — tone matters more than content
- If patient seems very anxious, spend extra time normalizing
- Some patients will immediately share their reason for being here — that's fine, let it flow naturally
