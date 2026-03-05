# Phase 3: Teacher Resources (Online) Check — TR (Yellow)

## Purpose
QA check loop for the teacher resources online content. Uses the data collected during Phase 2 teacher resources scraping.

## Data Sources
- Scraped teacher resources content from Phase 2
- QAC checklist Google Sheet (check instructions in this category)
- Teacher Edition PDF (TE)
- Printables
- Refer to `ai_rules.md` for what to skip

## Loop
1. Agent performs each TR (online) check from the checklist
2. Evaluates against the scraped teacher resources data and Teacher Edition PDF (TE)
3. If something is wrong → write QA comment to sheet
4. Repeat until all TR online checks are done

## What Is Being Checked
- Presence of certain media files
- Continuity and consistency between text in teacher resources and text in the Teacher Edition PDF
- Spelling errors/typos
- grammar errors

## Notes
