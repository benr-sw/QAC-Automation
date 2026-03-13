"""
Quick test: scrape first 3 TR articles and print structured output to verify
article_resources, week_resources, and lesson_plan_text are captured correctly.
Also dumps raw page content to check what selectors need updating.
"""
import os, json, logging
from dotenv import load_dotenv
load_dotenv("/Users/benrickers/Desktop/Vibes/QAC Automation/.env")
from playwright.sync_api import sync_playwright

PASSWORD = os.getenv("SW_PORTAL_PASSWORD")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test_tr")

import sys
sys.path.insert(0, "/Users/benrickers/Desktop/Vibes/QAC Automation")
from src.portal import (
    login, navigate_to_publication_toc, navigate_to_week,
    _get_current_article_title, _click_next, _navigate_to_first_article,
    _scrape_tr_article, SKIP_ARTICLE_KEYWORDS
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    login(page, PASSWORD, logger)
    navigate_to_publication_toc(page, "TN", 6, logger)
    navigate_to_week(page, 23, logger)

    # Click TEACHER RESOURCES tab
    tr_tab = page.locator("text=TEACHER RESOURCES").first
    tr_tab.click()
    page.wait_for_timeout(2000)
    print("Clicked TEACHER RESOURCES tab")

    _navigate_to_first_article(page, logger)

    # Skip walkthrough if first
    first = _get_current_article_title(page)
    print(f"First article: {first}")
    if any(kw in first.lower() for kw in ["walkthrough"]):
        print("  Skipping walkthrough...")
        _click_next(page)
        page.wait_for_timeout(2000)

    results = []
    for i in range(1, 15):
        title = _get_current_article_title(page)
        print(f"\n--- TR Article {i}: {title} ---")
        if any(kw in title.lower() for kw in SKIP_ARTICLE_KEYWORDS):
            print("  [STOP]")
            break

        art = _scrape_tr_article(page, i, title, logger)
        results.append(art)
        print(f"  sections ({len(art['sections'])}):")
        for sec in art['sections']:
            if sec['type'] == 'attachments':
                print(f"    [{sec['name']}] → attachments: {sec['items']}")
            else:
                preview = sec.get('content', '')[:120].replace('\n', ' / ')
                print(f"    [{sec['name']}] → {preview!r}")

        _click_next(page)
        page.wait_for_timeout(2000)

    with open("logs/test_tr_scrape.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n\nSaved to logs/test_tr_scrape.json")
    browser.close()
