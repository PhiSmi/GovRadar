"""Orchestrate a full scrape + enrich + store run."""

from __future__ import annotations

import logging
import sys
from datetime import date, timedelta

from db.queries import create_scrape_run, get_existing_tender_urls, update_scrape_run, upsert_tender
from scraper.enricher import enrich_all
from scraper.gets_scraper import scrape_gets
from scraper.notifications import build_run_summary, send_slack_summary, write_run_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _compute_metrics(rows: list[dict]) -> tuple[int, int]:
    high_relevance = sum(1 for row in rows if int(row.get("relevance_score", 0) or 0) >= 70)
    cutoff = date.today() + timedelta(days=21)
    closing_soon = 0
    for row in rows:
        if row.get("status") != "open":
            continue
        closing_date = row.get("closing_date")
        if not closing_date:
            continue
        try:
            row_date = date.fromisoformat(str(closing_date))
        except ValueError:
            continue
        if date.today() <= row_date <= cutoff:
            closing_soon += 1
    return high_relevance, closing_soon


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for row in rows:
        gets_url = row.get("gets_url")
        if gets_url:
            by_url[gets_url] = row
    return list(by_url.values())


def _warmup_db() -> None:
    """Wake Supabase if it has paused due to inactivity (free tier)."""
    from db.client import get_write_client
    try:
        get_write_client().select("tenders", params={"select": "id", "limit": "1"})
        logger.info("Database connection warmed up.")
    except Exception as exc:
        logger.warning("DB warmup ping failed (will retry normally): %s", exc)


def run(max_pages: int = 11):
    run_id: str | None = None
    errors: list[str] = []

    try:
        _warmup_db()
        run_id = create_scrape_run()

        tenders = scrape_gets(max_pages=max_pages)
        logger.info("Scraped %s relevant tenders", len(tenders))

        if not tenders:
            summary = build_run_summary([], new_count=0, errors=[])
            write_run_summary(summary)
            update_scrape_run(run_id, found=0, new=0, high_relevance=0, closing_soon=0, summary=summary)
            logger.info("No tenders found; done.")
            return

        enriched = _dedupe_rows(enrich_all(tenders))
        existing_urls = get_existing_tender_urls([row["gets_url"] for row in enriched if row.get("gets_url")])

        new_count = 0
        for row in enriched:
            try:
                gets_url = row.get("gets_url")
                is_new = bool(gets_url) and gets_url not in existing_urls
                row["scrape_run_id"] = run_id
                upsert_tender(row)
                if is_new:
                    new_count += 1
            except Exception as error:
                message = f"DB error for {row.get('title', '?')}: {error}"
                logger.error(message)
                errors.append(message)

        high_relevance, closing_soon = _compute_metrics(enriched)
        summary = build_run_summary(enriched, new_count=new_count, errors=errors)
        write_run_summary(summary)

        try:
            if send_slack_summary(summary):
                logger.info("Posted run summary to Slack.")
        except Exception as error:
            slack_error = f"Slack notification failed: {error}"
            logger.error(slack_error)
            errors.append(slack_error)

        update_scrape_run(
            run_id,
            found=len(enriched),
            new=new_count,
            high_relevance=high_relevance,
            closing_soon=closing_soon,
            summary=summary,
            errors="; ".join(errors) if errors else None,
        )
        logger.info(
            "Done - %s found, %s new, %s high relevance, %s closing soon, %s errors",
            len(enriched),
            new_count,
            high_relevance,
            closing_soon,
            len(errors),
        )

    except Exception as error:
        logger.exception("Fatal error in scrape run: %s", error)
        if run_id:
            try:
                update_scrape_run(
                    run_id,
                    found=0,
                    new=0,
                    high_relevance=0,
                    closing_soon=0,
                    summary="GovRadar scrape failed before completion.\n",
                    errors=str(error),
                )
            except Exception as update_error:
                logger.error("Could not update scrape run status: %s", update_error)
        sys.exit(1)


if __name__ == "__main__":
    run()
