# Phase 2: Student View Scraping

## Purpose
Before the sv (online) QA checks run, the agent iterates through every article in the student view of the week and collects all relevant content. This data is then used during the SV (online) QA check loop.

## Starting Point
The agent is already logged in, has opened the week's module dropdown via the plus (+) icon, and clicked into Student View. See `portal_reference.md` for navigation details.

## Loop — For Each Dropdown Article
The agent repeats the following for every item in the student view dropdown:

1. Click into the next dropdown item / article - OR clicks Next
2. Scrape the dropdown/article title
3. Scrape the full article text
4. Scrape the article images (descriptions or filenames)
5. Check if the article has questions
   - If yes → note the questions and all answer options
6. Check if the article has additional video media
   - If yes → note the media title
7. Repeat until the last article in the list

## What Gets Collected
- [ ] Dropdown titles for all articles
- [ ] Full text of each article
- [ ] Image references for each article
- [ ] Questions and answer options (where present)
- [ ] Video/media titles (where present)

## Output
All collected data is stored in memory and passed to the SV (online) check loop in Phase 3.

## Notes
- There are typically 4-12 articles in a given week. They'll typically look something like this:
   - Article: Essential Question
   - Article: Vocabulary
   - Article: Intro: Intro Article Title
   - Article 1: Article Title
   - Article 2: Article Title
   - Article 3: Article Title
   - Article 4: Article Title
   - Article 5: Weekly Connection
   - Assessment Week 23: Week Name Assessment
- Dropdowns can be labeled as articles, activities, or something else, but titles should be continuous across SE and TE
- Under the dropdown is a pagination that you can also use to navigate articles just the same
- You will not scrape the crossword article or the misspilled article
- Agent does not scrape the first walkthrough slide article content
