# Portal Reference — Studies Weekly Online (SWO)

## Purpose
Shared reference for all steps that involve navigating the SWO portal. Any step file that involves the portal should refer back here for common patterns.

## Login
- URL: https://online.studiesweekly.com/login
- Username: claudecode
- Password: stored in `.env` as `SW_PORTAL_PASSWORD`

## Navigation to Correct Week
After login, the agent must:
1. Identify the correct class module using the state code and grade number (e.g. state=TN, grade=6 → find module labeled TN6-8). Click on the module label.
2. Click into the correct grade card within that module. It will be labeled with subtext (e.g Sixth Grade)
3. Locate the correct week and click the plus (+) icon to open the module dropdown
4. This is where the checks in `docs/workflow/phase1_week_toc-check.md` take place

## Navigation in Student View
After navigating to the correct week the agent must:
1. Click into the TOC week title
2. Ensure that `Student View` near the top of the page is selected
3. The current page/article title in student view will be displayed in the dropdown box
4. Navigate to subsequent pages by clicking `Next` underneath the dropdown
5. You will interact with all pages by clicking `Next` until you reach the crossword page. You interact with the crossword page or any pages past it. 
6. Click `Previous` to go back and interact with previous pages

## Notes for Student View
1. You will not scrape, scan, or analyze the Walkthrough page because you've already been given the walkthrough slides to analyze as a PDF
2. Your directive is to scrape and analyze text and images throughout these pages.
3. Your directive is NOT to collect coins, watch videos, or listen to audio

## Navigation in Teacher Resources
The Teacher Resources page is accessible from the same point as Student view. To access, the agent must:
1. Click `Teacher Resources` near the top of the page
2. The current page/article title in Teacher Resources will be displayed in the dropdown box
4. Navigate to subsequent pages by clicking `Next` underneath the dropdown
5. You will interact with all pages by clicking `Next` until you reach the crossword page. You interact with the crossword page or any pages past it. 
6. Click `Previous` to go back and interact with previous pages

## Notes for Teacher Resources
1. You will not scrape, scan, or analyze the Walkthrough page because you've already been given the walkthrough slides to analyze as a PDF
2. Your directive is to scrape and analyze text and images throughout these pages.
3. Many of the sections are repeated on every teacher resource page. This is normal.
4. You will be analyzing the text from these pages and comparing it with the text on the Teacher Edition PDF (TE PDF)



## Session Notes
- Session may timeout if inactive for too long
- Login persists across page navigations
- If any pop-ups or modals appear, click X to close them

## Common Selectors / Page Patterns
- The class module cards are in the DOM in a grid pattern. The identifying text you're looking for and clicking on is at the top of the cards.
- Grade cards are organized in the DOM in a grid pattern. You'll identify the correct grade cards by seeing the grade number written as text (e.g. Sixth Grade, Seventh Grade, Eighth Grade). You'll click directly on the card, do NOT click the label on the card that says `View`
- Week rows are displayed within `Unit` modules. If you do not see Week rows upon entering this page, click the (+) icon to drop the units down to reveal the Week rows
- The week row also has a (+) icon which when clicked reveals the week content/articles as sub-rows. The (+) icon is on the left side of the week row.
- The week row also has up to five icons inside it on the right:
    - A grey PDF icon (accesses the printables)
    - A pink PDF icon (Accesses the assessment)
    - A purple reading icon (Accesses the student edition)
    - a blue teacher icon (Accesses the teacher resources)
    - A settings icon (settings for the module, to be ignored)

## Notes for portal navigation
- You will never click anything in the blue navigation bar at the top of the page
- You will never click the buttons on the left navigation bar labeled: Publications, Teacher Notes, Customized Content, People, Grade, Reports, Classroom settings
- You will not analyze the Lesson Walkthrough pages, because these are the walkthrough slides you already have the PDF for
- You will never click the "Teacher Actions" button in Student View and Teacher Resources pages
- You will never click the Teacher Edition or Student Edition buttons in the Teacher Resources page
- You can navigate between articles in Student View and Teacher Resources either by clicking `Previous` and `Next` or by selecting from the dropdown where the article title is.
