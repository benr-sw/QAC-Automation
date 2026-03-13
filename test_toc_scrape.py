"""
Quick test: verify scrape_toc_page DOM extraction for TN Gr1 Week 19.
Expected: Lesson Walkthrough + all articles + Assessment/Crossword/Misspilled
NOT expected: Assessment Unit 3 (unit-level, not week-level)
"""
import os, json, logging, sys
sys.path.insert(0, "/Users/benrickers/Desktop/Vibes/QAC Automation")
from dotenv import load_dotenv
load_dotenv("/Users/benrickers/Desktop/Vibes/QAC Automation/.env")
from playwright.sync_api import sync_playwright
from src.portal import login, navigate_to_publication_toc, scrape_toc_page

PASSWORD = os.getenv("SW_PORTAL_PASSWORD")
logging.basicConfig(level=logging.DEBUG, format="%(message)s")
logger = logging.getLogger("test_toc")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    login(page, PASSWORD, logger)
    navigate_to_publication_toc(page, "TN", 1, logger)

    toc = scrape_toc_page(page, 19, logger)

    print("\n=== TOC RESULT ===")
    print(f"Week: {toc['week']}")
    print(f"Icons: {toc['week_icons']}")
    print(f"Articles ({len(toc['articles'])}):")
    for a in toc["articles"]:
        print(f"  [{a['order']}] type='{a['type']}' title='{a['title']}'")

    browser.close()
