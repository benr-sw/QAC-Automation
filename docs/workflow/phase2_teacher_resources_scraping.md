# Phase 2: Teacher Resources Scraping

## Purpose
After scraping the student view, the agent navigates to the Teacher Resources section and collects all relevant content. This data is used during the TR (online) QA check loop.

## Starting Point
Agent has finished student view scraping and now clicks into Teacher Resources.

## Loop — For Each Dropdown Article
The agent repeats the following for every item in the teacher resources dropdown:

1. Click into the next dropdown item / article or Click the `Next` Pagination button
2. Scrape the dropdown title
3. Scrape all article resources
4. Scrape all week-level resources
5. Scrape all Unit-level resources
6. Scrape titles for all attached media
7. Repeat until the last article in the list

## What Gets Collected
- [ ] Dropdown titles for all articles
- [ ] Article week-level resources for each article
- [ ] Article unit-level resources for each article

## Output
All collected data is stored in memory and passed to the TR (online) check loop in Phase 2.

## Notes
- Typically printables and/or assessments and/or other documents may be listed in the articles. Titles should be noted, but these items do not need scraping or downloading
- Teacher Resources is available to click into near the top of the page right next to Student View
- Teacher Resources differs in view from student view
- Teacher Resources has many of the same text boxes from page to page
- Lesson Plans are the main things that differ across pages/articles
- Lesson Plans do not appear on every page
- You can navigate to each section of the article by clicking the hyperlinks on the right of the page
