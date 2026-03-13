"""
Quick test: scrape first 2 SV articles and print structured output to verify
text, audio, images, questions, and explore_more are captured correctly.
"""
import os, json, logging, re
from dotenv import load_dotenv
load_dotenv("/Users/benrickers/Desktop/Vibes/QAC Automation/.env")
from playwright.sync_api import sync_playwright

PASSWORD = os.getenv("SW_PORTAL_PASSWORD")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("test_sv")

# Import portal helpers after path fix
import sys
sys.path.insert(0, "/Users/benrickers/Desktop/Vibes/QAC Automation")
from src.portal import (
    login, navigate_to_publication_toc, navigate_to_week,
    scrape_student_view, _get_current_article_title, _click_next,
    _scrape_sv_article, _scrape_assessment_article, SKIP_ARTICLE_KEYWORDS
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    login(page, PASSWORD, logger)
    navigate_to_publication_toc(page, "TN", 6, logger)
    navigate_to_week(page, 23, logger)

    # Enter student view
    sv_tab = page.locator("text=STUDENT VIEW").first
    if sv_tab.is_visible(timeout=3000):
        sv_tab.click()
        page.wait_for_timeout(1500)

    # Skip walkthrough
    first = _get_current_article_title(page)
    print(f"\nSkipping walkthrough: {first}")
    _click_next(page)
    page.wait_for_timeout(2000)

    # Scrape all articles until stop keyword
    results = []
    for i in range(1, 20):
        title = _get_current_article_title(page)
        print(f"\n--- Article {i}: {title} ---")
        if any(kw in title.lower() for kw in SKIP_ARTICLE_KEYWORDS):
            print("  [STOP — skip keyword found]")
            break
        if "assessment" in title.lower():
            art = _scrape_assessment_article(page, i, title, logger)
        else:
            art = _scrape_sv_article(page, i, title, logger)
        results.append(art)
        print(f"  has_audio : {art['has_audio']}")
        print(f"  has_video : {art['has_video']}")
        print(f"  text len  : {len(art['text'])} chars")
        print(f"  text start: {art['text'][:120]!r}")
        print(f"  images    : {[img['alt'][:40] + (' (cap)' if img.get('caption') else '') for img in art['images']]}")
        print(f"  questions : {len(art['questions'])} found")
        for j, q in enumerate(art['questions']):
            print(f"    Q{j+1}: {q[:120]!r}")
        print(f"  explore_more: {art['explore_more']}")
        _click_next(page)
        page.wait_for_timeout(2000)

    with open("logs/test_sv_scrape.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n\nSaved to logs/test_sv_scrape.json")
    browser.close()
