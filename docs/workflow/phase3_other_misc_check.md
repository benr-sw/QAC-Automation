# Phase 2: Other / Miscellaneous Checks (Purple)

## Purpose
The final QA check loop. Covers checks that don't fall neatly into the other five categories — may draw from multiple data sources.

## Data Sources
- Any combination of: portal data, PDFs, printables, walkthrough slides
- QAC checklist Google Sheet (check instructions in this category)
- Refer to `ai_rules.md` for what to skip

## Loop
1. Agent performs each Other/Misc. check from the checklist
2. Evaluates against the relevant source for each check
3. If something is wrong → write QA comment to sheet
4. Repeat until all Other/Misc. checks are done → workflow ends

## What Is Being Checked
- [What types of checks fall in this category?]
- [Does the printables PDF get checked here? The walkthrough slides?]
- [Are there cross-document checks in this category?]

## Notes
- [Any known issues or common failures in this category]
- This is the final loop — when complete, the workflow ends and the user is shown the "All done!" screen with a link to the finished sheet
