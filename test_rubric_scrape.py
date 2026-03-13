"""
Test: scrape the Rubric TR article for NY5 Week 22 and verify rubric table extraction.
"""
import os, json, sys, logging
sys.stdout = open("/tmp/test_rubric_out.txt", "w", buffering=1)
sys.stderr = sys.stdout

sys.path.insert(0, "/Users/benrickers/Desktop/Vibes/QAC Automation")
from dotenv import load_dotenv
load_dotenv("/Users/benrickers/Desktop/Vibes/QAC Automation/.env")
from playwright.sync_api import sync_playwright
from src.portal import (
    login, navigate_to_publication_toc, navigate_to_week, _wait,
    _get_current_article_title, _click_next, _scrape_tr_article, SKIP_ARTICLE_KEYWORDS
)

PASSWORD = os.getenv("SW_PORTAL_PASSWORD")
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
logger = logging.getLogger("test_rubric")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    login(page, PASSWORD, logger)
    navigate_to_publication_toc(page, "NY", 5, logger)
    navigate_to_week(page, 22, logger)

    tr_tab = page.locator("text=TEACHER RESOURCES").first
    if tr_tab.is_visible(timeout=3000):
        tr_tab.click()
        _wait(page, 2000)

    for i in range(20):
        title = _get_current_article_title(page)
        if "rubric" in title.lower():
            print(f"\n=== Found Rubric article: {title!r} ===")
            result = _scrape_tr_article(page, i + 1, title, logger)
            print(f"\nSections ({len(result['sections'])}):")
            for sec in result["sections"]:
                print(f"\n  [{sec['type']}] {sec['name']!r}")
                if sec["type"] == "text":
                    print(f"  content:\n{sec['content']}")
                elif sec["type"] == "attachments":
                    for item in sec["items"]:
                        print(f"    - {item}")
            break
        if any(kw in title.lower() for kw in SKIP_ARTICLE_KEYWORDS): break
        if not _click_next(page): break
        _wait(page, 1500)

    browser.close()
    print("\n=== DONE ===")
