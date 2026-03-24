import json
import os
import queue
from datetime import datetime
from dotenv import load_dotenv
import anthropic

from src.logger import setup_logger
from src import sheets, portal, pdf_extractor, continuity, qa_engine


def run_workflow(
    sheet_url: str,
    pdf_files: dict,
    log_queue: queue.Queue,
    result_queue: queue.Queue,
    classroom_override: str = None,
):
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    logger = setup_logger(log_queue)
    playwright_instance = None
    browser = None

    try:
        # ---- Setup ----
        logger.info("Starting QAC workflow...")

        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        sw_password = os.getenv("SW_PORTAL_PASSWORD")
        service_account_path = os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/service_account.json"
        )

        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        if not sw_password:
            raise ValueError("SW_PORTAL_PASSWORD not set in .env")

        claude_client = anthropic.Anthropic(api_key=anthropic_key)

        # ---- Create timestamped run folder ----
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        run_dir = os.path.join(project_root, "logs", "runs", f"run_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        logger.info(f"Run output folder: {run_dir}")

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
            classroom_override=classroom_override,
        )

        # ---- Phase 1: Scrape TOC ----
        logger.info("--- Phase 1: Scraping TOC ---")
        toc_data = portal.scrape_toc_page(page, metadata["week_number"], logger)
        logger.info(f"  TOC articles found: {len(toc_data.get('articles', []))}")

        # ---- Phase 2: Scrape Student View ----
        logger.info(f"--- Phase 2: Clicking into Week {metadata['week_number']} ---")
        portal.navigate_to_week(page, metadata["week_number"], logger)

        sv_start_url = page.url
        logger.info("--- Phase 2: Scraping Student View ---")
        sv_articles = portal.scrape_student_view(page, logger)

        if not toc_data.get("articles"):
            toc_data["articles"] = [
                {
                    "type": a["title"].split(":")[0].strip(),
                    "title": ":".join(a["title"].split(":")[1:]).strip(),
                    "order": a["order"],
                }
                for a in sv_articles
            ]
            logger.info(
                f"  TOC articles built from SV scrape: {len(toc_data['articles'])} articles"
            )

        logger.info(f"  Scraped {len(sv_articles)} SV articles:")
        for a in sv_articles:
            if a.get("toc_only"):
                logger.info(f"    [{a['order']}] {a['title']} — (TOC stub, not scraped)")
            else:
                preview = a.get("text", "")[:120].replace("\n", " ")
                logger.info(f"    [{a['order']}] {a['title']} — \"{preview}\"")

        # ---- Phase 3: Scrape Teacher Resources ----
        logger.info("--- Phase 3: Scraping Teacher Resources ---")
        tr_articles = portal.scrape_teacher_resources(page, logger, sv_start_url=sv_start_url)
        logger.info(f"  Scraped {len(tr_articles)} TR articles:")
        for a in tr_articles:
            section_names = [s["name"] for s in a.get("sections", [])]
            preview = ", ".join(section_names[:4]) if section_names else "(no sections)"
            logger.info(f"    [{a['order']}] {a['title']} — sections: {preview}")

        # Save scraped JSON to run folder
        scraped_json_path = os.path.join(run_dir, "scraped.json")
        with open(scraped_json_path, "w") as f:
            json.dump(
                {"toc_data": toc_data, "sv_articles": sv_articles, "tr_articles": tr_articles},
                f,
                indent=2,
            )
        logger.info(f"  Scraped data saved → {scraped_json_path}")

        # ---- Phase 4: Extract PDFs via Claude ----
        logger.info("--- Phase 4: Extracting PDFs ---")
        extracted_files = {}
        for doc_type in ("SE", "TE", "Walkthrough", "Printables"):
            output_path = os.path.join(run_dir, f"extracted_{doc_type.lower()}.md")
            result = pdf_extractor.extract_pdf(
                claude_client,
                pdf_files.get(doc_type),
                doc_type,
                output_path,
                logger,
            )
            extracted_files[doc_type] = result  # None if not provided

        # ---- Phase 5: Continuity Analysis ----
        logger.info("--- Phase 5: Continuity Analysis ---")
        continuity_path = os.path.join(run_dir, "continuity_analysis.md")
        continuity.run_continuity_analysis(
            claude_client,
            scraped_json_path,
            extracted_files,
            continuity_path,
            logger,
        )

        # ---- Phase 6: Map issues to sheet and write ----
        logger.info("--- Phase 6: Writing issues to QAC sheet ---")
        checklist_rows = sheets.read_checklist_rows(worksheet)
        logger.info(f"  Read {len(checklist_rows)} checklist rows from sheet")

        mappings = qa_engine.map_issues_to_sheet(
            claude_client,
            continuity_path,
            checklist_rows,
            logger,
        )

        sheets.write_issue_batch(worksheet, mappings, logger)

        # ---- Done ----
        logger.info(f"Pipeline complete. All outputs saved to: {run_dir}")
        result_queue.put({"status": "done", "sheet_url": sheet_url, "run_dir": run_dir})

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        result_queue.put({"status": "error", "message": str(e)})

    finally:
        if browser and playwright_instance:
            portal.close_browser(playwright_instance, browser)
