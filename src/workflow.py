import json
import os
import queue
from datetime import datetime
from dotenv import load_dotenv
import anthropic

from src.logger import setup_logger
from src import sheets, pdf_parser, portal, qa_engine


def run_workflow(
    sheet_url: str,
    pdf_files: dict,
    log_queue: queue.Queue,
    result_queue: queue.Queue,
):
    load_dotenv()
    logger = setup_logger(log_queue)
    playwright_instance = None
    browser = None

    try:
        # ---- Setup ----
        logger.info("Starting QAC workflow...")

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        sw_password = os.getenv("SW_PORTAL_PASSWORD")
        service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service_account.json")

        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        if not sw_password:
            raise ValueError("SW_PORTAL_PASSWORD not set in .env")

        claude_client = anthropic.Anthropic(api_key=anthropic_key)

        # ---- Google Sheet ----
        logger.info("Connecting to Google Sheet...")
        sheet_id = sheets.extract_sheet_id(sheet_url)
        gspread_client = sheets.get_gspread_client(service_account_path)
        spreadsheet = sheets.open_sheet(gspread_client, sheet_id)
        worksheet = sheets.get_checklist_worksheet(spreadsheet)

        logger.info("Reading checklist metadata...")
        metadata = sheets.read_metadata(worksheet)
        logger.info(
            f"  State: {metadata['state']}, Grade: {metadata['grade']}, "
            f"Week: {metadata['week_number']} — {metadata['week_title']}"
        )

        logger.info("Reading checklist rows...")
        checklist_rows = sheets.read_checklist_rows(worksheet)
        logger.info(f"  Found {len(checklist_rows)} check items.")

        # ---- Parse PDFs ----
        logger.info("Parsing uploaded PDFs...")
        pdf_texts = {}
        for label, file_obj in pdf_files.items():
            if file_obj is not None:
                parsed = pdf_parser.extract_text_from_pdf(file_obj, label)
                pdf_texts[label] = parsed
                logger.info(f"  {label} PDF: {parsed['page_count']} pages")
            else:
                pdf_texts[label] = {"label": label, "page_count": 0, "full_text": "", "pages": []}
                logger.info(f"  {label} PDF: not provided")

        # ---- Portal: Login + Navigate ----
        logger.info("Launching browser...")
        playwright_instance, browser, context, page = portal.launch_browser(headless=False)

        logger.info("Logging into SWO portal...")
        portal.login(page, sw_password, logger)

        logger.info(
            f"Navigating to {metadata['state']} Grade {metadata['grade']} "
            f"Week {metadata['week_number']}..."
        )
        portal.navigate_to_publication_toc(
            page,
            metadata["state"],
            metadata["grade"],
            logger,
        )

        # ---- Phase 1: Scrape TOC ----
        logger.info("--- Phase 1: Scraping TOC ---")
        toc_data = portal.scrape_toc_page(page, metadata["week_number"], logger)
        logger.info(f"  TOC articles found: {len(toc_data.get('articles', []))}")

        # ---- Phase 2: Scrape Student View ----
        logger.info(f"--- Phase 2: Clicking into Week {metadata['week_number']} ---")
        portal.navigate_to_week(page, metadata["week_number"], logger)

        logger.info("--- Phase 2: Scraping Student View ---")
        sv_articles = portal.scrape_student_view(page, logger)

        # If the TOC accordion didn't expose article-level detail (some publications
        # only show week titles), build the article list from the scraped SV articles
        # (including toc_only stubs for crossword/misspilled/etc.).
        if not toc_data.get("articles"):
            toc_data["articles"] = [
                {"type": a["title"].split(":")[0].strip(), "title": ":".join(a["title"].split(":")[1:]).strip(), "order": a["order"]}
                for a in sv_articles
            ]
            logger.info(f"  TOC articles built from SV scrape: {len(toc_data['articles'])} articles")

        logger.info(f"  Scraped {len(sv_articles)} SV articles:")
        for a in sv_articles:
            if a.get("toc_only"):
                logger.info(f"    [{a['order']}] {a['title']} — (TOC stub, not scraped)")
            else:
                preview = a.get("text", "")[:120].replace("\n", " ")
                logger.info(f"    [{a['order']}] {a['title']} — \"{preview}\"")

        # ---- Phase 3: Scrape Teacher Resources ----
        logger.info("--- Phase 3: Scraping Teacher Resources ---")
        tr_articles = portal.scrape_teacher_resources(page, logger)
        logger.info(f"  Scraped {len(tr_articles)} TR articles:")
        for a in tr_articles:
            section_names = [s["name"] for s in a.get("sections", [])]
            preview = ", ".join(section_names[:4]) if section_names else "(no sections)"
            logger.info(f"    [{a['order']}] {a['title']} — sections: {preview}")

        # Write full scraped data to a debug JSON file for inspection
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_path = f"logs/scraped_{timestamp}.json"
        os.makedirs("logs", exist_ok=True)
        with open(debug_path, "w") as f:
            json.dump({
                "toc_data": toc_data,
                "sv_articles": sv_articles,
                "tr_articles": tr_articles,
            }, f, indent=2)
        logger.info(f"  Full scraped data saved to {debug_path}")

        # ---- Phase 4: QA Checks ----
        logger.info("--- Phase 4: TOC Checks ---")
        qa_engine.run_toc_checks(claude_client, toc_data, pdf_texts, checklist_rows, worksheet, logger)

        logger.info("--- Phase 4: SV Online Checks ---")
        sv_articles_content = [a for a in sv_articles if not a.get("toc_only")]
        qa_engine.run_sv_checks(claude_client, sv_articles_content, pdf_texts, checklist_rows, worksheet, logger)

        logger.info("--- Phase 4: TR Online Checks ---")
        qa_engine.run_tr_checks(claude_client, tr_articles, pdf_texts, checklist_rows, worksheet, logger)

        logger.info("--- Phase 4: SE PDF Checks ---")
        qa_engine.run_se_pdf_checks(claude_client, pdf_texts, checklist_rows, worksheet, logger)

        logger.info("--- Phase 4: TE PDF Checks ---")
        qa_engine.run_te_pdf_checks(claude_client, sv_articles_content, pdf_texts, checklist_rows, worksheet, logger)

        logger.info("--- Phase 4: Other/Misc Checks ---")
        all_data = {"toc_data": toc_data, "sv_articles": sv_articles_content, "tr_articles": tr_articles}
        qa_engine.run_other_checks(claude_client, all_data, pdf_texts, checklist_rows, worksheet, logger)

        # ---- Done ----
        logger.info("QAC workflow complete!")
        result_queue.put({"status": "done", "sheet_url": sheet_url})

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        result_queue.put({"status": "error", "message": str(e)})

    finally:
        if browser and playwright_instance:
            portal.close_browser(playwright_instance, browser)
