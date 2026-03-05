# Phase 1: Week Level / TOC Check (Pink)

## Purpose
The first QA check loop in the workflow. The agent verifies week-level and table of contents items against the checklist.

## Data Sources
- Portal (the week/module page navigated to. See `docs/workflow/portal_reference.md` for details on navigating to this level)
- Printables PDF
- Student Edition PDF
- Teacher Edition PDF
- QAC checklist Google Sheet (check instructions in this category)

## Loop
1. Agent locates the unit and week on the portal
2. Agent clicks into the week
3. Agent performs each week-level / TOC check from the checklist
4. If something is wrong → write QA comment to sheet
5. Repeat until all week-level checks are done

## What Is Being Checked
- The agent is checking that the sub-modules in the TOC dropdown correspond to the articles and sections (including their order) present in the Student and Teacher edition PDFs
- The agent is checking that the info in the printables, student edition, and teacher edition, is the correct week number and week title
- When the agent is performing the checks asking if certain documents are present it can assume they are if the user inputed that specific document (printables, student edition, teacher edition), or if the icon on the right of the week module is present (must spcecifically check that assessment icon is present)
    - See icon descriptions in `docs/workflow/portal_reference.md` in the Common Selectors / Page Patterns section

## Notes
- further descriptions and instructions for some checks can be found in the cell notes for the checks. Not all cells have notes
