import os
import re
import logging
from playwright.sync_api import sync_playwright, Page, Browser

PORTAL_LOGIN_URL = "https://online.studiesweekly.com/login"
PORTAL_BASE_URL = "https://online.studiesweekly.com"

GRADE_NAMES = {
    0: "Kindergarten",
    1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth",
    6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
    11: "Eleventh", 12: "Twelfth",
}

SKIP_ARTICLE_KEYWORDS = [
    "crossword", "misspilled", "word search"
]


# ---- Browser lifecycle ----

def launch_browser(headless: bool = False):  # headless=True for production
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    return playwright, browser, context, page


def close_browser(playwright, browser):
    try:
        browser.close()
        playwright.stop()
    except Exception:
        pass


def _wait(page: Page, ms: int = 2000):
    page.wait_for_timeout(ms)


# ---- Login ----

def login(page: Page, password: str, logger: logging.Logger):
    logger.info("Navigating to SWO login page...")
    page.goto(PORTAL_LOGIN_URL)
    page.wait_for_load_state("networkidle")
    _wait(page, 1000)

    username = os.getenv("SW_PORTAL_USERNAME")
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    try:
        page.wait_for_url(lambda url: "/login" not in url, timeout=60000)
    except Exception:
        raise RuntimeError("Login failed — still on login page. Check credentials.")
    page.wait_for_load_state("networkidle")
    logger.info("Logged in successfully.")


# ---- Navigation ----

def navigate_to_publication_toc(page: Page, state: str, grade: int, logger: logging.Logger, classroom_override: str = None) -> str:
    """
    From the classrooms page, navigates to the publication's Table of Contents page.
    Returns the TOC page URL.
    """
    _wait(page, 1000)

    classroom_cards = page.locator(".classroom-card").all()
    pub_path = None
    for card in classroom_cards:
        try:
            title = card.locator(".v-card__title").first.inner_text().strip().upper()
        except Exception:
            title = card.inner_text().split("\n")[0].strip().upper()

        # If override provided, match by card name directly
        if classroom_override:
            if classroom_override.upper() in title:
                view_all = card.locator("a.show-all-text")
                pub_path = view_all.get_attribute("href")
                logger.info(f"Found classroom card '{title}' via override. Publications path: {pub_path}")
                break
            continue

        # Auto-detect: find card whose title contains the state and grade
        if not title.startswith(state.upper()):
            continue

        range_match = re.search(r"(\d+)-(\d+)", title)
        if range_match:
            low, high = int(range_match.group(1)), int(range_match.group(2))
            if low <= grade <= high:
                view_all = card.locator("a.show-all-text")
                pub_path = view_all.get_attribute("href")
                logger.info(f"Found classroom card '{title}'. Publications path: {pub_path}")
                break
        else:
            kinder_match = grade == 0 and bool(re.search(r"K", title))
            single = re.search(r"(\d+)", title)
            if kinder_match or (single and int(single.group(1)) == grade):
                view_all = card.locator("a.show-all-text")
                pub_path = view_all.get_attribute("href")
                logger.info(f"Found classroom card '{title}'. Publications path: {pub_path}")
                break

    if not pub_path:
        if classroom_override:
            raise RuntimeError(f"Could not find classroom card matching override '{classroom_override}'")
        raise RuntimeError(f"Could not find classroom card for state={state}, grade={grade}")

    # Step 2: Navigate to publications page
    page.goto(f"{PORTAL_BASE_URL}{pub_path}")
    _wait(page, 3000)

    # Step 3: Find the publication card for the correct grade, click View >
    grade_name = GRADE_NAMES.get(grade, str(grade))
    view_btns = page.locator(".view-btn").all()
    clicked = False
    for btn in view_btns:
        parent = btn.locator("xpath=ancestor::div[3]").first
        card_text = parent.inner_text()
        match_str = grade_name if grade == 0 else f"{grade_name} Grade"
        if match_str in card_text:
            btn.click()
            _wait(page, 2000)
            clicked = True
            logger.info(f"Clicked View > for {grade_name} Grade.")
            break

    if not clicked:
        raise RuntimeError(f"Could not find publication for {grade_name} Grade")

    # Step 4: Click Table of Contents
    page.locator("text=Table of Contents").first.click()
    _wait(page, 3000)
    logger.info(f"On TOC page: {page.url}")
    return page.url


def navigate_to_week(page: Page, week_number: int, logger: logging.Logger):
    """
    From the publication TOC page, clicks into the correct week.
    Leaves the browser on the first article of the week (Lesson Walkthrough).
    """
    week_row = page.locator(f"text=Week {week_number}").first
    if not week_row.is_visible(timeout=5000):
        raise RuntimeError(f"Could not find Week {week_number} on TOC page.")

    week_row.click()
    _wait(page, 3000)
    logger.info(f"Clicked Week {week_number}. Now at: {page.url}")


# ---- TOC Scraping ----

def scrape_toc_page(page: Page, week_number: int, logger: logging.Logger) -> dict:
    """
    Called while on the publication TOC page, BEFORE clicking into the week.
    Scrapes article list directly from the DOM accordion for Week N.
    Returns the week module and its sub-articles in structured form.

    DOM structure (confirmed):
      div.week-card
        header.week-toolbar [area-owns="week{id}-articles"]
          div.week-toolbar-1
            div[role='button'][aria-expanded]  ← expand/collapse toggle
          div.week-toolbar-title
            .week-title a                      ← week title text
        div#week{id}-articles                  ← only present when expanded
          ol > li.article-list__item           ← one per article
            .v-subheader                       ← type label (e.g. "Article 1", "Lesson Walkthrough")
            .toc-article-level-title           ← article title
    """
    logger.info(f"Scraping TOC for Week {week_number}...")

    # --- Locate the week card ---
    week_text = f"Week {week_number}"
    try:
        week_el = page.locator(f"text='{week_text}'").first
        week_card = week_el.locator("xpath=ancestor::*[contains(@class,'week-card')][1]").first
    except Exception as e:
        logger.warning(f"Could not locate week-card for {week_text}: {e}")
        return {"week": {"number": week_number, "title": ""}, "week_icons": {}, "articles": []}

    # --- Week title ---
    week_title = ""
    try:
        week_title = week_card.locator(".week-title a, .week-title").first.inner_text().strip()
    except Exception:
        pass

    # --- Find articles container ID from header's area-owns attribute ---
    articles_id = ""
    try:
        header = week_card.locator("header.week-toolbar").first
        articles_id = header.evaluate("el => el.getAttribute('area-owns') || ''")
    except Exception as e:
        logger.debug(f"Could not read area-owns: {e}")

    # --- Ensure the week is expanded (click only if collapsed) ---
    try:
        expand_btn = week_card.locator("[role='button'][aria-expanded]").first
        btn_state = expand_btn.evaluate("el => el.getAttribute('aria-expanded')")
        if btn_state == "false":
            logger.debug(f"Week {week_number} is collapsed — expanding...")
            expand_btn.click()
            _wait(page, 2500)
            _exp_state = expand_btn.evaluate("el => el.getAttribute('aria-expanded')")
            logger.debug(f"Expanded. aria-expanded={_exp_state}")
        else:
            logger.debug(f"Week {week_number} already expanded (aria-expanded={btn_state})")
    except Exception as e:
        logger.debug(f"Expand button check: {e}")

    # --- Extract articles from the DOM container ---
    articles = []
    if articles_id:
        try:
            container = page.locator(f"#{articles_id}")
            if not container.is_visible(timeout=3000):
                logger.warning(f"Articles container #{articles_id} not visible after expand attempt")
            else:
                items = container.locator("li.article-list__item").all()
                logger.debug(f"Found {len(items)} article items in #{articles_id}")
                for item in items:
                    try:
                        # Type: full inner text of .v-subheader (captures both article-order-no
                        # and the Lesson Walkthrough type span that sits alongside it)
                        type_text = item.locator(".v-subheader").first.inner_text().strip()
                        # Collapse internal whitespace/newlines to single spaces
                        type_text = " ".join(type_text.split())
                        # Title: .toc-article-level-title
                        title_text = item.locator(".toc-article-level-title").first.inner_text().strip()
                        if type_text and title_text:
                            articles.append({
                                "type": type_text,
                                "title": title_text,
                                "order": len(articles) + 1,
                            })
                            logger.debug(f"  TOC article: [{type_text}] {title_text}")
                    except Exception as e:
                        logger.debug(f"  Article item parse error: {e}")
        except Exception as e:
            logger.warning(f"DOM article extraction failed: {e}")
    else:
        logger.warning(f"No articles_id found for Week {week_number} — article list will be empty")

    # --- Icon detection scoped to the week card ---
    icons = {}
    try:
        week_html = week_card.evaluate("el => el.outerHTML").lower()
        icons["student_edition"] = "student-edition" in week_html or "/se/" in week_html or "studentedition" in week_html
        icons["printables"] = "/printable" in week_html or "printable_icon" in week_html
        icons["teacher_edition"] = "teacher-edition" in week_html or "teacheredition" in week_html or "/te/" in week_html
        icons["assign"] = "/assign" in week_html or "assign_icon" in week_html
    except Exception as e:
        logger.warning(f"Icon detection error: {e}")

    logger.info(f"TOC: Week {week_number} '{week_title}' — {len(articles)} articles, icons={icons}")
    return {
        "week": {"number": week_number, "title": week_title},
        "week_icons": icons,
        "articles": articles,
    }


# ---- Student View Scraping ----

def scrape_student_view(page: Page, logger: logging.Logger) -> list[dict]:
    """
    Called after navigate_to_week. Starts on the Lesson Walkthrough (first article).
    Clicks Next to skip it, then iterates all articles collecting content.
    Stops at Crossword, Misspilled, or Assessment.
    """
    logger.info("Scraping Student View articles...")
    _wait(page, 1000)

    # Make sure we're in STUDENT VIEW
    sv_tab = page.locator("text=STUDENT VIEW").first
    if sv_tab.is_visible(timeout=3000):
        sv_tab.click()
        _wait(page, 1500)

    # Skip the Lesson Walkthrough only if it's actually the first article
    current_title = _get_current_article_title(page)
    if "walkthrough" in current_title.lower():
        logger.info(f"First article: {current_title} — skipping (Lesson Walkthrough)")
        _click_next(page)
        _wait(page, 2000)
    else:
        logger.info(f"First article: {current_title} — no Lesson Walkthrough, scraping from first article")

    # Record starting week URL to detect week-boundary crossings
    import re as _svre
    _week_id_match = _svre.search(r'/week/([^/]+)/', page.url)
    _start_week_id = _week_id_match.group(1) if _week_id_match else None

    articles = []
    order = 1
    seen_titles = set()
    MAX_ARTICLES = 30
    _last_valid_url = page.url  # track last URL inside correct week for TR restoration

    while order <= MAX_ARTICLES:
        current_title = _get_current_article_title(page)
        logger.info(f"Scraping SV article {order}: {current_title}")

        # Walkthrough articles mid-sequence: skip over them, keep scraping what follows
        title_lower = current_title.lower()
        if "walkthrough" in title_lower:
            logger.info(f"Skipping mid-sequence walkthrough: {current_title}")
            seen_titles.add(current_title)
            if not _click_next(page):
                break
            _wait(page, 2000)
            order += 1
            continue

        # Skip articles (crossword, misspilled, word search) — collect as TOC stub
        # but keep clicking Next in case scrapeable articles come after them.
        if any(kw in title_lower for kw in SKIP_ARTICLE_KEYWORDS):
            if _start_week_id:
                _s_match = _svre.search(r'/week/([^/]+)/', page.url)
                if not _s_match or _s_match.group(1) != _start_week_id:
                    logger.debug(f"TOC stub loop: week boundary hit, restoring to {_last_valid_url}")
                    page.goto(_last_valid_url)
                    _wait(page, 1500)
                    break
            _last_valid_url = page.url
            articles.append({
                "title": current_title, "order": order,
                "text": "", "has_audio": False, "has_video": False,
                "images": [], "questions": [], "explore_more": [],
                "toc_only": True,
            })
            logger.info(f"  TOC stub: {current_title}")
            seen_titles.add(current_title)
            order += 1
            if not _click_next(page):
                break
            _wait(page, 1000)
            continue

        # Stop if URL's week ID changed (crossed into a different week)
        if _start_week_id:
            _cur_match = _svre.search(r'/week/([^/]+)/', page.url)
            if _cur_match and _cur_match.group(1) != _start_week_id:
                logger.info(f"Week boundary detected (URL changed). Restoring to {_last_valid_url} for TR.")
                page.goto(_last_valid_url)
                _wait(page, 1500)
                break

        # Stop if we've looped back to a title we've already seen
        if current_title in seen_titles:
            logger.info(f"Detected repeated title '{current_title}' — stopping SV to avoid loop.")
            break
        seen_titles.add(current_title)

        if "assessment" in current_title.lower():
            article = _scrape_assessment_article(page, order, current_title, logger)
        else:
            article = _scrape_sv_article(page, order, current_title, logger)
        articles.append(article)
        _last_valid_url = page.url  # update after successful scrape, before clicking next

        # Try to go to next article
        if not _click_next(page):
            logger.info("No more Next button. Done with SV.")
            break
        _wait(page, 2000)
        order += 1

    if order > MAX_ARTICLES:
        logger.warning(f"SV scraping hit MAX_ARTICLES limit ({MAX_ARTICLES}). Stopping.")

    logger.info(f"Scraped {len(articles)} student view articles.")
    return articles


def _get_current_article_title(page: Page) -> str:
    try:
        title = page.locator(".article-select-reponsive, .v-select.article-select-responsive").first.inner_text().strip()
        return title.replace("\u200b", "").strip()
    except Exception:
        try:
            return page.locator("h1, h2").first.inner_text().strip()
        except Exception:
            return "Unknown"


def _navigate_to_first_article(page: Page, logger: logging.Logger):
    """Select the first article in the dropdown to reset navigation position."""
    try:
        dropdown = page.locator(".article-select-reponsive, .v-select.article-select-responsive").first
        dropdown.click()
        _wait(page, 1000)
        # Scope to the Vuetify menu overlay to avoid matching page navigation items
        first_item = page.locator(".v-menu__content .v-list-item, .menuable__content__active .v-list-item").first
        if first_item.is_visible(timeout=3000):
            first_item.click()
            _wait(page, 1500)
            logger.info(f"Reset to first article: {_get_current_article_title(page)}")
        else:
            page.keyboard.press("Escape")
            logger.warning("Could not find first dropdown item — proceeding from current position.")
    except Exception as e:
        logger.warning(f"Could not navigate to first article: {e}")


def _click_next(page: Page) -> bool:
    try:
        next_btn = page.locator("button:has-text('Next')").first
        if next_btn.is_visible(timeout=2000) and next_btn.is_enabled():
            next_btn.click()
            return True
        return False
    except Exception:
        return False


_NOISE_LINES = frozenset({
    "the highlighted text does not contain any vocabulary words.",
    "the highlighted text does not contain vocabulary words.",
    "no vocabulary words",
    "collect coins",
    "collecting coins",
})

_LOGO_ALT_NOISE = frozenset({
    "studies weekly", "studies weekly logo", "logo", "no content", ""
})


_ACTIVE_MENU = ".v-menu__content.menuable__content__active.v-autocomplete__content"


def _get_fib_blank_options(page: Page, question_container) -> list[list[str]]:
    """
    Click each .blank-select dropdown within a question container, capture the
    options from the active Vuetify autocomplete menu, then close it.
    Returns a list of option lists, one per blank.
    """
    blank_options = []
    blanks = question_container.locator(".blank-select").all()
    for blank in blanks:
        try:
            blank.click()
            menu = page.locator(_ACTIVE_MENU)
            menu.wait_for(state="visible", timeout=3000)
            raw_items = menu.locator(".v-list-item").all_inner_texts()
            # Deduplicate — Vuetify sometimes renders each item twice
            seen: set[str] = set()
            unique = []
            for item in raw_items:
                item = item.strip()
                if item and item not in seen:
                    seen.add(item)
                    unique.append(item)
            blank_options.append(unique)
            page.keyboard.press("Escape")
            menu.wait_for(state="hidden", timeout=2000)
        except Exception:
            blank_options.append([])
    return blank_options


def _scrape_assessment_article(page: Page, order: int, title: str, logger: logging.Logger) -> dict:
    """
    Scrapes an Assessment article in Student View.
    Returns structured question data in `assessment_questions`:
      - multiple_choice: text + choices[]
      - open_response: text only
      - fill_in_blank: text (with [___] for blanks) + blank_options[[]]
      - grouping: text + grouping_categories[] + grouping_terms[]
    """
    result = {
        "title": title,
        "order": order,
        "type": "assessment",
        "text": "",
        "has_audio": False,
        "has_video": False,
        "images": [],
        "questions": [],
        "explore_more": [],
        "assessment_questions": [],
    }

    # Scroll to bottom so all questions render
    try:
        page.evaluate("""() => {
            const c = document.getElementById('container');
            if (c) c.scrollTop = c.scrollHeight;
            else window.scrollTo(0, document.body.scrollHeight);
        }""")
        _wait(page, 2000)
    except Exception:
        pass

    # Scrape all questions via JS (everything except FIB blank options)
    try:
        questions = page.evaluate("""() => {
            const _strip = (t) => t.replace(/^\\d+\\s*\\n+\\s*\\d+\\s*\\n+/, '').trim();
            const _fib_clean = (t) => t.replace(/\\u200b/g, '[___]').trim();

            const containers = document.querySelectorAll('.question-container');
            return [...containers].map((qc, idx) => {
                const q = { number: idx + 1 };

                // Type detection
                q.type = qc.querySelector('.mult-question-wrapper')         ? 'multiple_choice' :
                         qc.querySelector('.open-response-question-wrapper') ? 'open_response'  :
                         qc.querySelector('.fib-question-wrapper')           ? 'fill_in_blank'  :
                         qc.querySelector('.grouping-question-wrapper')      ? 'grouping'       :
                         qc.querySelector('.matching-question-wrapper')      ? 'matching'       :
                         qc.querySelector('.sorting-question-wrapper')       ? 'sorting'        :
                         qc.querySelector('.label-image-wrapper, .map-label-wrapper, [class*="label-image"], [class*="map-question"]') ? 'image_label' : 'unknown';

                // Question text
                const qtcEl = qc.querySelector('.question-text-container, .question-text');
                const rawText = qtcEl ? qtcEl.innerText.trim() : '';
                q.text = q.type === 'fill_in_blank'
                    ? _fib_clean(_strip(rawText))
                    : _strip(rawText);

                // Matching: text is in .v-html.matching_question
                if (q.type === 'matching' && !q.text) {
                    const mq = qc.querySelector('.matching_question, .v-html.matching_question');
                    q.text = mq ? _strip(mq.innerText.trim()) : '';
                }

                // Grouping: fall back to container first line if no text element
                if (!q.text && q.type === 'grouping') {
                    const lines = _strip(qc.innerText.trim()).split('\\n').map(l => l.trim()).filter(l => l);
                    q.text = lines[0] || '';
                }

                // image_label: map/image labeling questions — capture label options as choices
                if (q.type === 'image_label') {
                    if (!q.text) {
                        const allLines = _strip(qc.innerText.trim()).split('\\n').map(l => l.trim()).filter(l => l);
                        q.text = allLines[0] ? allLines[0].substring(0, 300) : '';
                    }
                    // Label options may appear as draggable items or option elements
                    const labelItems = [...qc.querySelectorAll('[class*="label-item"], [class*="drag-item"], [class*="option"], .qst-option-wrapper')];
                    if (labelItems.length > 0) {
                        q.choices = labelItems.map(el => el.innerText.trim()).filter(t => t);
                    }
                }

                // Unknown types (e.g. text annotation/underline):
                // Treat as open_response and use container first non-empty line as text.
                if (q.type === 'unknown') {
                    q.type = 'open_response';
                    if (!q.text) {
                        const allLines = _strip(qc.innerText.trim()).split('\\n').map(l => l.trim()).filter(l => l);
                        q.text = allLines.slice(0, 2).join(' ').substring(0, 300);
                    }
                }

                // MC choices
                q.choices = [...qc.querySelectorAll('.choice-card')].map(c => {
                    const opt = c.querySelector('.option_text');
                    return (opt ? opt.innerText : c.innerText).trim();
                }).filter(t => t);

                // Grouping categories + terms
                q.grouping_categories = [];
                q.grouping_terms = [];
                if (q.type === 'grouping') {
                    q.grouping_categories = [...qc.querySelectorAll('.grouping-question-drop-area')]
                        .map(da => (da.innerText.trim().split('\\n').map(l => l.trim()).filter(l => l)[0] || ''))
                        .filter(c => c);
                    if (q.grouping_categories.length === 0) {
                        // Parse category names from full text
                        const lines = _strip(qc.innerText.trim()).split('\\n').map(l => l.trim()).filter(l => l);
                        q.grouping_categories = lines.slice(1, 3);
                    }
                    q.grouping_terms = [...qc.querySelectorAll('.grouping-question-terms .qst-option-wrapper')]
                        .map(t => t.innerText.trim()).filter(t => t);
                }

                // Matching terms (drop zones, left side) + options (right side draggable pool)
                // Structure: .drop-zone .synth-text = term labels; .qst-option-wrapper .option_text = options
                q.matching_terms = [];
                q.matching_options = [];
                if (q.type === 'matching') {
                    q.matching_terms = [...qc.querySelectorAll('.drop-zone .synth-text')]
                        .map(el => el.innerText.trim()).filter(t => t);
                    q.matching_options = [...qc.querySelectorAll('.qst-option-wrapper .option_text, .qst-option-wrapper .text-content')]
                        .map(el => el.innerText.trim()).filter(t => t);
                    // Fallback: if option_text selector missed, use qst-option-wrapper directly
                    if (q.matching_options.length === 0) {
                        q.matching_options = [...qc.querySelectorAll('.qst-option-wrapper')]
                            .map(el => el.innerText.trim()).filter(t => t);
                    }
                }

                // Sorting: text is in [data-cy="sorting-question"]; items in .term .option_text
                if (q.type === 'sorting') {
                    if (!q.text) {
                        const sq = qc.querySelector('[data-cy="sorting-question"]');
                        q.text = sq ? _strip(sq.innerText.trim()) : '';
                    }
                    q.choices = [...qc.querySelectorAll('.term .qst-option-wrapper .option_text')]
                        .map(el => el.innerText.trim()).filter(t => t);
                }

                // FIB blank options populated later (requires click interactions)
                q.blank_options = [];

                // Images embedded in the question (e.g. "Study the image." questions)
                const LOGO_NOISE = new Set(['', 'logo', 'studies weekly', 'studies weekly logo', 'no content']);
                q.images = [...qc.querySelectorAll('img')]
                    .map(img => img.alt ? img.alt.trim() : '')
                    .filter(alt => alt && !LOGO_NOISE.has(alt.toLowerCase()));

                return q;
            });
        }""")
    except Exception as e:
        logger.warning(f"Assessment scrape failed: {e}")
        return result

    # For each FIB question, click its blanks to get dropdown options
    q_containers = page.locator(".question-container").all()
    for q, qc in zip(questions, q_containers):
        if q["type"] == "fill_in_blank":
            q["blank_options"] = _get_fib_blank_options(page, qc)

    result["assessment_questions"] = questions
    logger.info(f"Assessment: scraped {len(questions)} questions.")
    return result


def _scrape_sv_article(page: Page, order: int, title: str, logger: logging.Logger) -> dict:
    result = {
        "title": title,
        "order": order,
        "text": "",
        "has_audio": False,
        "has_video": False,
        "images": [],
        "questions": [],
        "explore_more": [],
    }

    title_lower = title.lower()
    # EQ and Vocab articles are reference displays — their source_object content
    # is the article body, not student response questions.
    is_reference_article = (
        "essential question" in title_lower or
        (title_lower.startswith("article:") and "vocabulary" in title_lower)
    )
    # Reading articles (any grade) whose body text lives in .v-html.source_object.
    # For upper grades these tend to be long (> 500 chars); for KG they are short.
    # We use this flag to treat short source_object content as article text, not questions.
    is_article = title_lower.startswith("article") and not is_reference_article

    # ---- Audio ----
    try:
        result["has_audio"] = page.locator("audio#highlighter-main-audio-player").count() > 0
    except Exception:
        pass

    # ---- Video ----
    try:
        result["has_video"] = page.locator(
            "iframe[src*='youtube'], iframe[src*='vimeo'], video"
        ).count() > 0
    except Exception:
        pass

    # Scroll to bottom first so lazy-loaded elements (e.g. question boxes at
    # the end of long articles) are in the DOM before we query them.
    # The SPA uses #container (overflow:auto) as the scrollable viewport — NOT window.
    try:
        page.evaluate("""() => {
            const c = document.getElementById('container');
            if (c) c.scrollTop = c.scrollHeight;
            else window.scrollTo(0, document.body.scrollHeight);
        }""")
        _wait(page, 1500)
    except Exception:
        pass

    # ---- Article text ----
    # Strategy:
    #   1. Primary: <p> in .text_question_text NOT inside .v-html.source_object
    #      (standard reading articles where text and questions are separate).
    #   2. If nothing found, check total source_object text length:
    #      - If > 500 chars: annotation article (reading passage is in source_object)
    #        → use first highlightContainer paragraphs as text
    #      - If ≤ 500 chars: questions-only article (no article body, just prompts)
    #        → text = "" so questions capture all source_object content
    # Reference articles (EQ, Vocab) whose source_object is short get their text
    # directly from source_object paragraphs regardless of the length check.
    try:
        scraped = page.evaluate("""(args) => {
            const noiseLines = args.noiseLines;
            const isReference = args.isReference;

            // Primary: .text_question_text p NOT inside .v-html.source_object
            const primary = [...document.querySelectorAll('.text_question_text p')]
                .filter(p => !p.closest('.v-html.source_object'))
                .map(p => p.innerText.trim())
                .filter(t => t && !noiseLines.includes(t.toLowerCase()));

            if (primary.length > 0) return { source: 'primary', lines: primary };

            // No primary text found.
            // For reference articles (EQ, Vocab) the source_object IS the body.
            if (isReference) {
                const refLines = [...document.querySelectorAll('.v-html.source_object p')]
                    .map(p => p.innerText.trim())
                    .filter(t => t && !noiseLines.includes(t.toLowerCase()));
                return { source: 'reference', lines: refLines };
            }

            // Check total source_object text length to distinguish article types.
            const sourceLen = [...document.querySelectorAll('.v-html.source_object')]
                .reduce((acc, d) => acc + d.innerText.trim().length, 0);

            if (sourceLen > 500) {
                // Annotation article: article body is INSIDE source_object.
                for (const hc of document.querySelectorAll('.highlightContainer')) {
                    const lines = [...hc.querySelectorAll('p')]
                        .map(p => p.innerText.trim())
                        .filter(t => t && !noiseLines.includes(t.toLowerCase()));
                    if (lines.length > 0) return { source: 'fallback', lines: lines };
                }
            } else if (args.isArticle && sourceLen > 0) {
                // Short reading article (e.g. kindergarten): the source_object IS the body.
                const lines = [...document.querySelectorAll('.v-html.source_object p')]
                    .map(p => p.innerText.trim())
                    .filter(t => t && !noiseLines.includes(t.toLowerCase()));
                if (lines.length > 0) return { source: 'short_article', lines };
            }

            // Questions-only article: no article body at all.
            return { source: 'questions_only', lines: [] };
        }""", {"noiseLines": list(_NOISE_LINES), "isReference": is_reference_article, "isArticle": is_article})

        if scraped["lines"]:
            result["text"] = "\n\n".join(scraped["lines"])[:8000]
        text_from_fallback = scraped["source"] == "fallback"
        # Skip Strategy A when:
        # - source_object was already used as article text (short/reference articles)
        # - OR text was found via primary strategy on a standard article
        #   (source_object only contains headings/decorative content, not questions)
        skip_strategy_a = (
            scraped["source"] in ("short_article", "reference")
            or (is_article and scraped["source"] == "primary")
        )
    except Exception as e:
        logger.warning(f"Could not scrape article text: {e}")
        text_from_fallback = False
        skip_strategy_a = False

    # ---- Images ----
    # Inline article images use class 'skip-hl'; their captions live in a
    # sibling <span class="credit-caption-wrapper"> inside the same .embedded-image div.
    # Returns list of {"alt": str, "caption": str} dicts. Logos are filtered out.
    try:
        images = page.evaluate("""(noiseAlts) => {
            const LOGO_CLASSES = ['main-logo-lg', 'main-logo-sm', '_pendo-image',
                                   '_pendo-badge-image', '_pendo-resource-center-badge-image'];
            const imgs = document.querySelectorAll('img.skip-hl, img.sbp_image');
            const seen = new Set();
            const result = [];
            for (const img of imgs) {
                const alt = (img.alt || '').trim();
                if (!alt) continue;
                if (noiseAlts.includes(alt.toLowerCase())) continue;
                if ([...img.classList].some(c => LOGO_CLASSES.includes(c))) continue;
                if (seen.has(alt)) continue;
                seen.add(alt);
                // Caption is in a sibling span.credit-caption-wrapper in the same .embedded-image
                const embeddedDiv = img.closest('.embedded-image');
                const captionEl = embeddedDiv
                    ? embeddedDiv.querySelector('.credit-caption-wrapper')
                    : null;
                const caption = captionEl ? captionEl.innerText.trim() : '';
                result.push({ alt, caption });
            }
            return result;
        }""", list(_LOGO_ALT_NOISE))
        result["images"] = images
    except Exception:
        pass

    # ---- Questions ----
    # Two question structures exist in the portal:
    #
    # 1. Annotation articles (Article 3, 6, etc.): reading passage + student notes
    #    live inside .v-html.source_object divs. We capture paragraphs that don't
    #    duplicate the article text already captured above.
    #
    # 2. Activity articles (Activity 1, 2, etc.): numbered open-response questions
    #    in .review-question-block .question-text-container. These are only present
    #    after scrolling #container to the bottom (lazy-loaded).
    #
    # Reference articles (EQ, Vocab) are skipped entirely.
    if not is_reference_article:
        existing_text_lower = result["text"].lower()

        # Strategy A: .v-html.source_object (annotation articles)
        # Skipped when source_object content was already used as article text
        # (short reading articles like KG) or for reference articles.
        if not skip_strategy_a:
            try:
                for q_div in page.locator(".v-html.source_object").all():
                    question_paras = []
                    for p_el in q_div.locator("p").all():
                        p_text = p_el.inner_text().strip()
                        if not p_text:
                            continue
                        if p_text.lower() in _NOISE_LINES:
                            continue
                        # Skip paragraphs already captured in the article text
                        if p_text[:60].lower() in existing_text_lower:
                            continue
                        question_paras.append(p_text)
                    if question_paras:
                        q_text = "\n\n".join(question_paras)
                        if len(q_text) > 10:
                            result["questions"].append(q_text[:500])
            except Exception:
                pass

        # Strategy B: .question-text-container (works for Activity articles with
        # .review-question-block AND for standard Article articles that place questions
        # directly in .question-container without a .review-question-block wrapper).
        # Captures MC choices (A. B. C. D.) if present in the same parent container.
        # Suggested answers live in .suggested-answer-container — skip those as questions.
        # Always runs (not gated on Strategy A) because standard articles with MC/open-response
        # questions may also have .v-html.source_object content that Strategy A captures.
        if True:
            try:
                q_blocks = page.evaluate("""() => {
                    const NOISE = ['answers will vary', 'answers may vary', 'sample answer'];
                    const LETTERS = 'ABCDEFGHIJ';
                    const results = [];
                    for (const qtc of document.querySelectorAll('.question-text-container')) {
                        if (qtc.closest('.suggested-answer-container')) continue;
                        let text = qtc.innerText.trim();
                        // Strip repeated leading digit+newline prefixes from question text
                        text = text.replace(/^(\\d+\\s*\\n+)+/, '').trim();
                        if (!text) continue;
                        if (NOISE.some(n => text.toLowerCase().startsWith(n))) continue;
                        if (text.length <= 5) continue;

                        // Capture MC choices from the parent question container
                        const parent = qtc.closest('.question-container, .review-question-block') || qtc.parentElement;
                        const choices = parent
                            ? [...parent.querySelectorAll('.choice-card')].map(c => {
                                const opt = c.querySelector('.option_text');
                                return (opt ? opt.innerText : c.innerText).trim();
                              }).filter(t => t)
                            : [];

                        let full = text;
                        if (choices.length > 0) {
                            full += '\\n' + choices.map((c, i) => LETTERS[i] + '. ' + c).join('\\n');
                        }
                        results.push(full.substring(0, 800));
                    }
                    return results;
                }""")
                for q in q_blocks:
                    if q in result["questions"]:
                        continue
                    # Filter out section-navigation labels: short strings whose every
                    # line already appears verbatim in the article text (e.g. tab headers
                    # like "Culture\n\nGovernment" in multi-section Case Study articles).
                    if len(q) < 60:
                        q_lines = [l.strip() for l in q.split('\n') if l.strip()]
                        if q_lines and all(l.lower() in existing_text_lower for l in q_lines if len(l) > 2):
                            continue
                    result["questions"].append(q)
            except Exception:
                pass

    # ---- Explore More ----
    # The explore-more-block emits lines like:
    #   "Explore More\nImage\nBattle of Salamis\nVideo\nThe Persian Wars\nAudio\n..."
    # Parse into labeled entries: "Image: Battle of Salamis", "Video: The Persian Wars"
    try:
        emb = page.locator(".explore-more-block")
        if emb.count() > 0 and emb.first.is_visible(timeout=1000):
            raw = emb.first.inner_text().strip()
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            # Drop the "Explore More" header
            if lines and lines[0].lower() == "explore more":
                lines = lines[1:]

            MEDIA_TYPES = {"Image", "Video", "Audio", "Map"}
            FILTER_NOISE = {"coin", "collect", "submit"}

            parsed = []
            i = 0
            while i < len(lines):
                line = lines[i]
                # Skip noise content
                if any(n in line.lower() for n in FILTER_NOISE):
                    i += 1
                    continue
                if line in MEDIA_TYPES:
                    # Next line is the title
                    if i + 1 < len(lines):
                        title_text = lines[i + 1]
                        if not any(n in title_text.lower() for n in FILTER_NOISE):
                            parsed.append(f"{line}: {title_text}")
                        i += 2
                    else:
                        i += 1
                else:
                    # Unlabeled item — keep if it's not a media type label itself
                    if line not in MEDIA_TYPES and line.lower() != "explore more":
                        parsed.append(line)
                    i += 1
            result["explore_more"] = parsed[:15]
    except Exception:
        pass

    # Rubric articles have their content in a Vue component that only mounts on a
    # fresh page load — navigating via Next skips its data fetch.  Load via fresh context.
    if title.lower().startswith("rubric:"):
        _rubric_url = page.url
        logger.info("SV: rubric article — fetching via fresh browser context to load rubric table")
        _rubric_page = None
        _rubric_context = None
        try:
            _storage = page.context.storage_state()
            _rubric_context = page.context.browser.new_context(storage_state=_storage)
            _rubric_page = _rubric_context.new_page()
            import re as _re2
            _m = _re2.search(
                r'/teacher/classrooms/([^/]+)/publications/([^/]+)/units/([^/]+)/week/([^/]+)/',
                _rubric_url,
            )
            _base = "https://online.studiesweekly.com/teacher/classrooms"
            if _m:
                _cid, _pid, _uid, _wid = _m.group(1), _m.group(2), _m.group(3), _m.group(4)
                for _step_url in [
                    f"{_base}/{_cid}/publications",
                    f"{_base}/{_cid}/publications/{_pid}",
                    f"{_base}/{_cid}/publications/{_pid}/units/{_uid}/week/{_wid}",
                    _rubric_url,
                ]:
                    _rubric_page.goto(_step_url)
                    _rubric_page.wait_for_load_state("networkidle")
                    _wait(_rubric_page, 1000)
            else:
                _rubric_page.goto(_rubric_url)
                _rubric_page.wait_for_load_state("networkidle")
            try:
                _rubric_page.wait_for_selector(".rubric-table", timeout=8000)
            except Exception:
                _wait(_rubric_page, 2000)
            rubric_text = _rubric_page.evaluate("""() => {
                var table = document.querySelector('.rubric-table');
                if (!table) return null;
                var lines = [];
                var rows = table.querySelectorAll('.rubric-row');
                for (var i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    var headings = row.querySelectorAll('.rubric-heading');
                    var cells = row.querySelectorAll('.rubric-cell:not(.rubric-scores)');
                    var scoreEl = row.querySelector('.rubric-scores');
                    var score = scoreEl ? scoreEl.innerText.trim() : '';
                    if (headings.length > 0) {
                        var hTexts = [];
                        for (var h = 0; h < headings.length; h++) {
                            hTexts.push(headings[h].innerText.trim());
                        }
                        lines.push(hTexts.join(' | '));
                    } else if (cells.length > 0) {
                        var cTexts = [];
                        for (var c = 0; c < cells.length; c++) {
                            cTexts.push(cells[c].innerText.trim().replace(/\\n+/g, ' '));
                        }
                        if (score) cTexts.push(score);
                        lines.push(cTexts.join(' | '));
                    }
                }
                return lines.length ? lines.join('\\n') : null;
            }""")
            if rubric_text:
                logger.debug(f"SV: found rubric table with {rubric_text.count(chr(10)) + 1} rows")
                result["text"] = rubric_text
        except Exception as _ge:
            logger.warning(f"SV: fresh-context rubric load failed: {_ge}")
        finally:
            if _rubric_context:
                try:
                    _rubric_context.close()
                except Exception:
                    pass
            elif _rubric_page:
                try:
                    _rubric_page.close()
                except Exception:
                    pass

    return result


# ---- Teacher Resources Scraping ----

def scrape_teacher_resources(page: Page, logger: logging.Logger, sv_start_url: str = None) -> list[dict]:
    """
    Clicks the TEACHER RESOURCES tab and iterates through articles.
    """
    logger.info("Navigating to Teacher Resources...")

    # Navigate back to first article URL if provided — ensures we're on an article
    # page where the TEACHER RESOURCES tab is visible (not an assignments page)
    if sv_start_url:
        logger.info(f"Restoring to article page: {sv_start_url}")
        page.goto(sv_start_url)
        page.wait_for_load_state("networkidle")
        _wait(page, 2000)

    try:
        page.locator("text=TEACHER RESOURCES").first.wait_for(state="visible", timeout=30000)
        page.locator("text=TEACHER RESOURCES").first.click()
        _wait(page, 3000)
        logger.info("Clicked TEACHER RESOURCES tab.")
    except Exception:
        logger.warning("TEACHER RESOURCES tab not found.")
        return []

    # Reset to first article (tab switch inherits SV's last position)
    _navigate_to_first_article(page, logger)

    # Skip the first item only if it's actually a Lesson Walkthrough
    current_title = _get_current_article_title(page)
    if any(kw in current_title.lower() for kw in ["walkthrough", "lesson walkthrough"]):
        logger.info(f"Skipping first TR item: {current_title}")
        _click_next(page)
        _wait(page, 2000)
    else:
        logger.info(f"First TR item: {current_title} — no Lesson Walkthrough, scraping from first article")

    # Record starting week URL to detect week-boundary crossings
    import re as _trre
    _tr_week_match = _trre.search(r'/week/([^/]+)/', page.url)
    _tr_start_week_id = _tr_week_match.group(1) if _tr_week_match else None

    articles = []
    order = 1
    seen_titles = set()
    MAX_ARTICLES = 30

    while order <= MAX_ARTICLES:
        current_title = _get_current_article_title(page)
        title_lower = current_title.lower()

        if any(kw in title_lower for kw in SKIP_ARTICLE_KEYWORDS):
            logger.info(f"TR: skipping '{current_title}', continuing in case scrapeable articles follow.")
            seen_titles.add(current_title)
            order += 1
            if not _click_next(page):
                break
            _wait(page, 1000)
            continue

        # Stop if URL's week ID changed (crossed into a different week)
        if _tr_start_week_id:
            _tr_cur = _trre.search(r'/week/([^/]+)/', page.url)
            if _tr_cur and _tr_cur.group(1) != _tr_start_week_id:
                logger.info(f"Week boundary detected (URL changed). Done with TR.")
                break

        # Stop if we've looped back to a title we've already seen
        if current_title in seen_titles:
            logger.info(f"Detected repeated title '{current_title}' — stopping TR to avoid loop.")
            break
        seen_titles.add(current_title)

        logger.info(f"Scraping TR article {order}: {current_title}")
        article = _scrape_tr_article(page, order, current_title, logger)
        articles.append(article)

        if not _click_next(page):
            logger.info("No more Next button. Done with TR.")
            break
        _wait(page, 2000)
        order += 1

    if order > MAX_ARTICLES:
        logger.warning(f"TR scraping hit MAX_ARTICLES limit ({MAX_ARTICLES}). Stopping.")

    logger.info(f"Scraped {len(articles)} teacher resource articles.")
    return articles


def _get_tr_scope(panel_id: str) -> str:
    """Extract scope keyword (article/week/unit/publication) from a TR panel ID."""
    lower = panel_id.lower()
    for scope in ("article", "week", "unit", "publication"):
        if f"-{scope}-" in lower or lower.endswith(f"-{scope}"):
            return scope
    return "other"


# JS that extracts structured content from a list of TR panel links.
# Handles numbered/lettered lists (<ol>/<li>) and attachment type prefixes.
_TR_EXTRACT_JS = """
function(scopeLinks) {
    var GROUP_HEADERS = {
        "week resources": 1, "unit resources": 1,
        "publication resources": 1, "article resources": 1
    };
    var NOISE = {
        "the highlighted text does not contain any vocabulary words.": 1,
        "the highlighted text does not contain vocabulary words.": 1,
        "print": 1
    };
    var LOCALE_RE = /^language:/i;
    var ATTACH_TYPES = {"pdf": 1, "audio": 1, "image": 1, "video": 1, "media": 1};

    // For sections with ordered lists (lesson plans), do structured walk to preserve
    // numbering. For all other sections, innerText splitting is simpler and reliable.
    function tableToLines(table) {
        var rows = Array.from(table.querySelectorAll('tr'));
        return rows.map(function(row) {
            var cells = Array.from(row.querySelectorAll('th, td'));
            return cells.map(function(c) { return c.innerText.trim(); }).filter(function(c) { return !!c; }).join(' | ');
        }).filter(function(r) { return !!r; });
    }

    function extractLines(el) {
        var hasOL = !!el.querySelector('ol');
        var hasTable = !!el.querySelector('table');
        if (!hasOL && !hasTable) {
            // Simple innerText approach: works for vocab, TBK, EQ, attachments, etc.
            var raw = el.innerText.trim();
            return raw.split('\\n').map(function(l) { return l.trim(); }).filter(function(l) { return !!l; });
        }
        if (hasTable && !hasOL) {
            // Table-only content (rubrics, grids, etc.)
            var lines = [];
            Array.from(el.childNodes).forEach(function(node) {
                if (node.nodeType === 1) {
                    if (node.tagName === 'TABLE') {
                        lines = lines.concat(tableToLines(node));
                    } else {
                        var txt = node.innerText ? node.innerText.trim() : '';
                        if (txt) lines.push(txt);
                    }
                }
            });
            return lines.filter(function(l) { return !!l; });
        }

        // Structured walk for list-based content (lesson plans)
        var lines = [];

        function isHidden(node) {
            if (node.classList.contains('dragContext')) return true;
            if (node.classList.contains('leftHandle')) return true;
            if (node.classList.contains('rightHandle')) return true;
            var style = window.getComputedStyle(node);
            return style.display === 'none' || style.visibility === 'hidden';
        }

        function processNode(node, depth) {
            if (!node || node.nodeType !== 1) return;
            if (isHidden(node)) return;
            var tag = node.tagName;
            if (tag === 'OL') {
                var n = 0;
                Array.from(node.children).forEach(function(child) {
                    if (child.tagName === 'LI') { n++; processLI(child, depth, n); }
                });
            } else if (tag === 'UL') {
                Array.from(node.children).forEach(function(child) {
                    if (child.tagName === 'LI') { processLI(child, depth, null); }
                });
            } else if (tag === 'P') {
                var txt = node.innerText.trim();
                if (txt && !LOCALE_RE.test(txt)) lines.push(txt);
            } else if (tag === 'TABLE') {
                lines = lines.concat(tableToLines(node));
            } else {
                Array.from(node.children).forEach(function(child) {
                    processNode(child, depth);
                });
            }
        }

        function processLI(li, depth, num) {
            // Get direct text: first P child or first text node before any nested list
            var directText = '';
            var childNodes = Array.from(li.childNodes);
            for (var i = 0; i < childNodes.length; i++) {
                var child = childNodes[i];
                if (child.nodeType === 3) {
                    var t = child.textContent.trim();
                    if (t && !directText) directText = t;
                } else if (child.tagName === 'P' && !directText) {
                    directText = child.innerText.trim();
                    break;
                } else if (child.tagName === 'OL' || child.tagName === 'UL') {
                    break;
                }
            }

            var indent = new Array(depth + 1).join('  ');
            var prefix;
            if (num === null) prefix = indent + String.fromCharCode(8226) + ' ';
            else if (depth === 0) prefix = num + '. ';
            else prefix = indent + String.fromCharCode(64 + num) + '. ';

            if (directText && !LOCALE_RE.test(directText)) {
                lines.push(prefix + directText);
            }

            // Process nested lists
            Array.from(li.children).forEach(function(child) {
                if (child.tagName === 'OL' || child.tagName === 'UL') {
                    var subN = 0;
                    Array.from(child.children).forEach(function(subLi) {
                        if (subLi.tagName === 'LI') {
                            subN++;
                            processLI(subLi, depth + 1, subN);
                        }
                    });
                }
            });
        }

        Array.from(el.children).forEach(function(child) {
            processNode(child, 0);
        });
        return lines;
    }

    return scopeLinks.map(function(link) {
        var el = document.getElementById(link.panelId);
        if (!el) return null;

        var rawLines = extractLines(el);

        // Strip leading group headers and section name
        while (rawLines.length && GROUP_HEADERS[rawLines[0].toLowerCase().trim()]) {
            rawLines.shift();
        }
        if (rawLines.length && rawLines[0].trim().toLowerCase() === link.text.trim().toLowerCase()) {
            rawLines.shift();
        }

        // Filter noise
        var filtered = rawLines.filter(function(l) {
            return !NOISE[l.trim().toLowerCase()];
        });

        if (!filtered.length) return null;

        // Attachment section: a line contains only a known type label
        var isAttachment = filtered.some(function(l) {
            return ATTACH_TYPES[l.trim().toLowerCase()];
        });

        if (isAttachment) {
            var items = [];
            var bare = filtered.map(function(l) { return l.trim(); });
            for (var i = 0; i < bare.length; i++) {
                if (ATTACH_TYPES[bare[i].toLowerCase()] && i + 1 < bare.length
                        && !ATTACH_TYPES[bare[i + 1].toLowerCase()]) {
                    var typeLabel = bare[i].charAt(0).toUpperCase() + bare[i].slice(1);
                    items.push(typeLabel + ': ' + bare[i + 1]);
                    i++;
                }
            }
            if (!items.length) return null;
            return {name: link.text, type: 'attachments', items: items};
        } else {
            var content = filtered.join('\\n');
            if (!content.trim()) return null;
            return {name: link.text, type: 'text', content: content};
        }
    }).filter(function(s) { return s !== null; });
}
"""


def _scrape_tr_article(page: Page, order: int, title: str, logger: logging.Logger) -> dict:
    """
    Scrapes a single Teacher Resources article.

    Follows the right-panel hyperlink structure. Iterates all sidebar scope groups
    (Article → Week → Unit → Publication), clicking the first link in each scope to
    activate its panels, then extracts all sections for that scope.

    Each section is returned as:
      {name, type: 'text', content: str}       — structured text with list numbering
      {name, type: 'attachments', items: [...]} — "Type: Name" strings per document
    """
    result = {
        "title": title,
        "order": order,
        "sections": [],
    }

    try:
        page.wait_for_selector(".list-marker-primary a", timeout=5000)
    except Exception:
        pass

    # Collect all sidebar links
    links = page.evaluate("""
        Array.from(document.querySelectorAll('.list-marker-primary a'))
            .filter(function(a) {
                var h = a.getAttribute('href') || '';
                return h.charAt(0) === '#';
            })
            .map(function(a) {
                return {
                    text: a.innerText.trim(),
                    panelId: a.getAttribute('href').substring(1)
                };
            })
    """)

    if not links:
        return result

    # Group by scope in order: article → week → unit → publication
    from collections import OrderedDict
    scope_groups: OrderedDict = OrderedDict()
    for link in links:
        scope = _get_tr_scope(link["panelId"])
        if scope not in scope_groups:
            scope_groups[scope] = []
        scope_groups[scope].append(link)

    # Track seen names for cross-scope disambiguation
    seen_names: dict = {}
    all_sections = []

    for scope, scope_links in scope_groups.items():
        # Activate this scope by clicking its first link
        first_panel_id = scope_links[0]["panelId"]
        try:
            page.evaluate(
                "function(id) { var a = document.querySelector('a[href=\"#' + id + '\"]'); if (a) a.click(); }",
                first_panel_id,
            )
            _wait(page, 1500)
        except Exception as e:
            logger.warning(f"TR: could not activate scope '{scope}': {e}")
            continue

        # Extract each panel individually.
        # Some panels (e.g. Printables, Weekly Assessment PDF) are lazy-loaded and
        # only appear in the DOM after their specific sidebar link is clicked.
        for link in scope_links:
            panel_exists = False
            try:
                panel_exists = page.evaluate(
                    "(id) => !!document.getElementById(id)", link["panelId"]
                )
            except Exception:
                pass

            if not panel_exists:
                # Click this specific link to trigger its panel to load
                try:
                    page.evaluate(
                        "function(id) { var a = document.querySelector('a[href=\"#' + id + '\"]'); if (a) a.click(); }",
                        link["panelId"],
                    )
                    _wait(page, 800)
                except Exception as e:
                    logger.warning(f"TR: could not click link '{link['text']}': {e}")
                    continue

            try:
                sections = page.evaluate(f"({_TR_EXTRACT_JS})", [link])
            except Exception as e:
                logger.warning(f"TR: extract failed for '{link['text']}': {e}")
                continue

            for sec in sections:
                raw_name = sec["name"]
                if raw_name in seen_names:
                    sec["name"] = f"{raw_name} ({scope.capitalize()})"
                seen_names[raw_name] = seen_names.get(raw_name, 0) + 1
                all_sections.append(sec)

    result["sections"] = all_sections
    return result
