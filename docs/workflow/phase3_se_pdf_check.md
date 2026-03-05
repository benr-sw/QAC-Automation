# Phase 3: Student Edition PDF Check — SE (Green)

## Purpose
QA check loop for the Student Edition PDF uploaded by the user.

## Data Sources
- Student Edition PDF (uploaded by user via app UI)
- Teacher Edition PDF
- QAC checklist Google Sheet (check instructions in this category)
- Refer to `ai_rules.md` for what to skip

## Loop
1. Agent performs each SE (PDF) check from the checklist
2. Evaluates against the parsed Student Edition PDF content
3. If something is wrong → write QA comment to sheet
4. Repeat until all SE PDF checks are done

## What Is Being Checked
- Text accuracy
- Image accuracy
- Potential layout/formatting issues
- Typos, grammar, issues
- Video icons for articles with videos listed in the teacher edition
- Inconsistencies in formatting, spelling, names, etc. throughout

## PDF Parsing Notes
- PDF will not have standardized formatting
- Check all pages in PDF
- An AI will need to analyze the whole document
- Articles, columns, and tables may be placed differently throughout the PDF

## Notes
- The student edition PDF is a student workbook with activities, headings, articles, images, and vocabulary
