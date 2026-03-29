"""AI enrichment of tenders using Claude API."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

import anthropic

from scraper.gets_scraper import RawTender

logger = logging.getLogger(__name__)
_client: anthropic.Anthropic | None = None

ENRICHMENT_MODEL = "claude-sonnet-4-20250514"
ENRICHMENT_PROMPT_VERSION = "v2"

ENRICHMENT_PROMPT = """\
You are analysing a New Zealand government tender for a career-focused intelligence tool.

The user is a Senior Technical Business Analyst / Integration Analyst with 10+ years experience \
across NZ government, health, and banking sectors. Key skills: API design, integration architecture, \
AWS, Azure, Salesforce, data migration, requirements analysis, stakeholder management.

Analyse this tender and return a JSON object with these fields:
- probable_tech_stack: array of technologies likely involved
- probable_roles: array of roles this tender will likely need
- programme_size: one of "small", "medium", "large", "mega"
- relevance_score: 0-100 integer
- relevance_reasoning: one sentence explaining the score
- estimated_seek_timeline: one of "3 months", "6 months", "9 months", "12 months"
- themes: array of themes

Respond with ONLY the JSON object, no markdown fencing or explanation.

TENDER:
Title: {title}
Agency: {agency}
Type: {tender_type}
Category: {category}
Estimated Value: {estimated_value}

Tender Description:
{description}

Supporting Attachment Excerpt:
{attachment_excerpt}
"""


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY must be set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _coerce_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _coerce_score(value) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def enrich_tender(tender: RawTender, client: anthropic.Anthropic | None = None) -> dict:
    client = client or _get_client()

    prompt = ENRICHMENT_PROMPT.format(
        title=tender.title,
        agency=tender.agency or "Not specified",
        tender_type=tender.tender_type or "Not specified",
        category=tender.category or "Not specified",
        estimated_value=tender.estimated_value or "Not specified",
        description=(tender.description or "No description available")[:5000],
        attachment_excerpt=(tender.attachment_text_excerpt or "No attachment text available")[:2500],
    )

    try:
        response = client.messages.create(
            model=ENRICHMENT_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)
        return {
            "probable_tech_stack": _coerce_list(data.get("probable_tech_stack")),
            "probable_roles": _coerce_list(data.get("probable_roles")),
            "programme_size": data.get("programme_size", "medium"),
            "relevance_score": _coerce_score(data.get("relevance_score")),
            "relevance_reasoning": str(data.get("relevance_reasoning", ""))[:500],
            "estimated_seek_timeline": data.get("estimated_seek_timeline", "6 months"),
            "themes": _coerce_list(data.get("themes")),
        }
    except json.JSONDecodeError as error:
        logger.error("Failed to parse Claude response for '%s': %s", tender.title, error)
        return _empty_enrichment()
    except Exception as error:
        logger.error("Claude API error for '%s': %s", tender.title, error)
        return _empty_enrichment()


def _empty_enrichment() -> dict:
    return {
        "probable_tech_stack": [],
        "probable_roles": [],
        "programme_size": "medium",
        "relevance_score": 0,
        "relevance_reasoning": "Enrichment failed",
        "estimated_seek_timeline": "6 months",
        "themes": [],
    }


def enrich_all(tenders: list[RawTender], delay: float = 1.0) -> list[dict]:
    client = _get_client()
    results = []
    for index, tender in enumerate(tenders):
        logger.info("Enriching %s/%s: %s...", index + 1, len(tenders), tender.title[:60])
        enrichment = enrich_tender(tender, client=client)
        now = datetime.now(timezone.utc).isoformat()

        row = {
            "title": tender.title,
            "agency": tender.agency,
            "closing_date": tender.closing_date,
            "gets_url": tender.gets_url,
            "tender_type": tender.tender_type,
            "rfx_id": tender.rfx_id,
            "estimated_value": tender.estimated_value,
            "status": tender.status,
            "category": tender.category,
            "description": (tender.description or "")[:12000],
            "attachment_urls": tender.attachment_urls,
            "attachment_text_excerpt": (tender.attachment_text_excerpt or "")[:8000] or None,
            "date_scraped": tender.date_scraped or now,
            "last_seen_at": tender.date_scraped or now,
            "enrichment_model": ENRICHMENT_MODEL,
            "enrichment_prompt_version": ENRICHMENT_PROMPT_VERSION,
            "enrichment_updated_at": now,
            **enrichment,
        }
        results.append(row)

        if index < len(tenders) - 1:
            time.sleep(delay)

    return results
