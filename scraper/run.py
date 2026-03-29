"""Orchestrate a full scrape + enrich + store run."""

from __future__ import annotations
import logging
import sys

from scraper.gets_scraper import scrape_gets
from scraper.enricher import enrich_all
from db.queries import upsert_tender, tender_exists, create_scrape_run, update_scrape_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run(max_pages: int = 11):
    run_id: str | None = None
    errors: list[str] = []

    try:
        run_id = create_scrape_run()

        # 1. Scrape
        tenders = scrape_gets(max_pages=max_pages)
        logger.info(f"Scraped {len(tenders)} relevant tenders")

        if not tenders:
            update_scrape_run(run_id, found=0, new=0)
            logger.info("No tenders found — done.")
            return

        # 2. Enrich with AI
        enriched = enrich_all(tenders)

        # 3. Store
        new_count = 0
        for row in enriched:
            try:
                is_new = not tender_exists(row["gets_url"])
                row["scrape_run_id"] = run_id
                upsert_tender(row)
                if is_new:
                    new_count += 1
            except Exception as e:
                msg = f"DB error for {row.get('title', '?')}: {e}"
                logger.error(msg)
                errors.append(msg)

        update_scrape_run(
            run_id,
            found=len(enriched),
            new=new_count,
            errors="; ".join(errors) if errors else None,
        )
        logger.info(f"Done — {len(enriched)} found, {new_count} new, {len(errors)} errors")

    except Exception as e:
        logger.exception(f"Fatal error in scrape run: {e}")
        if run_id:
            try:
                update_scrape_run(run_id, found=0, new=0, errors=str(e))
            except Exception as update_error:
                logger.error(f"Could not update scrape run status: {update_error}")
        sys.exit(1)


if __name__ == "__main__":
    run()
