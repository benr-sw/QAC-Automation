# Phase 2: Student View (Online) Check — SV (Orange)

## Purpose
QA check loop for the student-facing online content. Uses the data collected during Phase 2 student view scraping.

## Data Sources
- Scraped student view content from Phase 2
- QAC checklist Google Sheet (check instructions in this category)
- Student Edition PDF (SE)
- Teacher Edition PDF (TE)
- Walkthrough slides
- Printables
- Refer to `ai_rules.md` for what to skip

## Loop
1. Agent performs each SV (online) check from the checklist
2. Evaluates against the scraped student view data, the TE, and the SE
3. If something is wrong → write QA comment to sheet
4. Repeat until all SV online checks are done

## What Is Being Checked
- article text accuracy
- image presence
- question formatting
- Article and text continuity between online and SE
- image continuity between online and SE
- Media and article title continuity between online and what's listed in the TE

## Notes
- Be sure to check if cell in google sheets has note with additional info
- The first few checks in this section are for the walkthrough slides which the user gave already
- Some images may be formatted differently in the SE than online, even if they're the same images
