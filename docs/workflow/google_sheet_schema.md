# Google Sheet Schema

## Purpose
The Agent will ONLY be working in columns A, B, and C of the QAC Checklist. Any column after C should be completely ignored.

## Inputs from the Sheet for the AI to know

| Cell | Content | Example |
|---|---|---|
| A2 | State and grade code | `TN-06` |
| A3 | Week number | `Week 23` |
| A4 | Week Title | `Growth and Conflict of Ancient Greece` |

- State code is the characters before the dash (e.g. `TN`)
- Grade number is the characters after the dash (e.g. `06` → 6)
- Week number should be parsed as an integer
- The info in these cells will have the cell labels in the same cell (e.g. `State and Grade #: TN-06`) so the AI will need to take the state and grade code, week number, or week title and exclude the label text

## QA Checklist Structure
The sheet contains the checklist items the agent uses to perform QA checks. Describe the structure here:

- The sheet labled `CHECKLIST` has the checklist items
- Column A after row 7 contains the check instructions
- The check category (Week Level, SV Online, TR Online, SE PDF, TE PDF, Other) is in column 7, same as the check instructions. The check category, and sub category lines are differentiated by being bolded or italicized and containing an emoji by the label. The categories and sub-categories read as follows:
    - 🗂️ Table of Contents - TOC (online)
        - 📑 Week level
    - 📚 Student View - SV (online)
        - 🖥🎞 Walkthrough - WT
        - ❓Essential question and supporting questions
        - 🔤 Vocabulary
        - 🌱 Intro article
        - 📖🔈 Article/activity text and audio
        - 📸  Images
        - 🔍 Article assessment questions
        - 🖼🎬🎶 Explore More / Related Media - RM
        - 🔗 Weekly connection
        - ➕📕 Extended reading - ER
        - 📝 Assessment 
        - 🧩 Crossword
        - 💰 Coins
    - 🧑‍🏫 Teacher Resources - TR (online)
        - 🗓 Week level
        - 📅 Article level
    - 📰 Student Edition - SE (print)
    - 📒 Teacher Edition (print)
    - ⚠️ Other/Miscellaneous
- For lines to skip, see the skip list in `docs/workflow/ai_rules.md`
- Checks are grouped by category, and should be performed in order down the spreadsheet. You'll find a new check in each row under a subcategory row until you reach the next category or subcategory.

## Writing QA Comments Back

- Cells in column B, after line 7, have the checkbox which should be checked if something is wrong on the check. Checkboxes do not appear in category or subcategory rows.
- QA Comments will go in column C
- The agent should write comments to the same row as the check item
- Comments should be written in plain text. At the beginning of the comment, the location in the materials of where the issue is should be specified. For example, if the issue is in Article or Activity 4, begin the comment with `Article 4 - `
- Sometimes multiple comments for the same check will be needed. If this happens, write multiple comments in the same cell, separated by a new line.

## Notes
- Permission to the sheet will need to be granted at the beginning of the app when the user is giving inputs. The app will need a mechanism to get access to a google drive folder where the sheet is located
- This is the structure for the QAC sheet most of the time. On occasion you'll receive a sheet with only some of the categories. If that is the case, only conduct checks for the categories/subcategories present on the sheet.
