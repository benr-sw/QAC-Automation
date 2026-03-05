# Phase 3: Teacher Edition PDF Check — TE (Blue)

## Purpose
QA check loop for the Teacher Edition PDF uploaded by the user.

## Data Sources
- Teacher Edition PDF (uploaded by user via app UI)
- QAC checklist Google Sheet (check instructions in this category)
- Refer to `ai_rules.md` for what to skip

## Loop
1. Agent performs each TE (PDF) check from the checklist
2. Evaluates against the parsed Teacher Edition PDF content
3. If something is wrong → write QA comment to sheet
4. Repeat until all TE PDF checks are done

## What Is Being Checked
- Typos, grammer, error
- That lesson and arrticle structure is consistent with online and student edition PDF
- Inconsistencies between spelling, names, questions, titles, assessment, etc. in the TE and online/student edition PDF

## PDF Parsing Notes
- Oftentimes the week assessment is included in the Teacher Edition
- All pages are relevant to check


