"""AI enrichment of tenders using Claude API."""

from __future__ import annotations
import json
import logging
import os
import time

import anthropic

from scraper.gets_scraper import RawTender

logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT = """\
You are analysing a New Zealand government tender for a career-focused intelligence tool.

The user is a Senior Technical Business Analyst / Integration Analyst with 10+ years experience \
across NZ government, health, and banking sectors. Key skills: API design, integration architecture, \
AWS, Azure, Salesforce, data migration, requirements analysis, stakeholder management.

Analyse this tender and return a JSON object with these fields:
- probable_tech_stack: array of technologies likely involved (e.g. ["AWS", "Salesforce", "REST APIs"])
- probable_roles: array of roles this tender will likely need (e.g. ["Business Analyst", "Solution Architect", "Developer"])
- programme_size: one of "small", "medium", "large", "mega"
- relevance_score: 0-100 integer — how relevant is this to the user's profile
- relevance_reasoning: one sentence explaining the score
- estimated_seek_timeline: when roles from this tender will likely appear on job boards — one of "3 months", "6 months", "9 months", "12 months"
- themes: array of themes (e.g. ["modernisation", "data migration", "regulatory", "greenfield", "integration"])

Respond with ONLY the JSON object, no markdown fencing or explanation.

TENDER:
Title: {title}
Agency: {agency}
Type: {tender_type}
Category: {category}
Estimated Value: {estimated_value}

Description:
{description}
"""


def enrich_tender(tender: RawTender) -> dict:
    """Call Claude to analyse a single tender. Returns enrichment fields dict."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    prompt = ENRICHMENT_PROMPT.format(
        title=tender.title,
        agency=tender.agency or "Not specified",
        tender_type=tender.tender_type or "Not specified",
        category=tender.category or "Not specified",
        estimated_value=tender.estimated_value or "Not specified",
        description=(tender.description or "No description available")[:4000],
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # Strip markdown fencing if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        data = json.loads(text)

        return {
            "probable_tech_stack": data.get("probable_tech_stack", []),
            "probable_roles": data.get("probable_roles", []),
            "programme_size": data.get("programme_size", "medium"),
            "relevance_score": int(data.get("relevance_score", 0)),
            "relevance_reasoning": data.get("relevance_reasoning", ""),
            "estimated_seek_timeline": data.get("estimated_seek_timeline", "6 months"),
            "themes": data.get("themes", []),
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Claude response for '{tender.title}': {e}")
        return _empty_enrichment()
    except Exception as e:
        logger.error(f"Claude API error for '{tender.title}': {e}")
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
    """Enrich a list of tenders, returning list of dicts ready for DB insert.

    Each dict merges the raw tender data with enrichment fields.
    """
    results = []
    for i, tender in enumerate(tenders):
        logger.info(f"Enriching {i + 1}/{len(tenders)}: {tender.title[:60]}...")
        enrichment = enrich_tender(tender)

        row = {
            "title": tender.title,
            "agency": tender.agency,
            "closing_date": tender.closing_date,
            "gets_url": tender.gets_url,
            "tender_type": tender.tender_type,
            "estimated_value": tender.estimated_value,
            "status": tender.status,
            "category": tender.category,
            "description": (tender.description or "")[:10000],
            **enrichment,
        }
        results.append(row)

        if i < len(tenders) - 1:
            time.sleep(delay)

    return results
