# AI Rules — Check Behavior

## Purpose
Defines which checks in the QA checklist the AI agent should avoid

## Skip List
The agent should skip any checklist item that involves:
- Listening to audio or a podcast
- Clicking into and watching video
- The Misspilled game
- The crossword
- Collecting coins
- Submitting questions or forms
- Clicking on answers for questions
- Testing podcast QR code

When a check is skipped, write "skipped" in the QA comments column.

## Check Logic
- The agent reads the check instructions from the Google Sheet checklist
- It evaluates the relevant content (portal page, PDF, etc.) against those instructions
- If something is wrong → it writes a QA comment to the sheet, and checks the QA box
- If nothing is wrong → it moves to the next check

## What "Something Wrong" Means
- For many of the checks, additional details are given in the cell notes. Something is wrong when the material in question does not match the check guidelines.
- It is a binary pass/fail - no severity score
- Be succinct in comments, describing what the issue is, and where it's located in the materials

## Notes
- Not everything with these checks is black and white. A good question to ask if you come across a potential issue is "Does this disrupt continuity between the materials, or give the reader a poorer experience?" If so, check the box in column B and leave a comment in column C.
