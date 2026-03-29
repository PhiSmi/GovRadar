from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from db.client import get_read_client, get_write_client


def _eq(value: str) -> str:
    return f"eq.{quote(str(value), safe='')}"


def _gte(value: int) -> str:
    return f"gte.{value}"


def get_tenders(
    status: str | None = None,
    min_relevance: int = 0,
    agency: str | None = None,
    category: str | None = None,
    limit: int = 200,
):
    params = {
        "select": "*",
        "order": "relevance_score.desc,closing_date.asc.nullslast",
        "limit": str(limit),
    }
    if status:
        params["status"] = _eq(status)
    if min_relevance > 0:
        params["relevance_score"] = _gte(min_relevance)
    if agency:
        params["agency"] = _eq(agency)
    if category:
        params["category"] = _eq(category)
    return get_read_client().select("tenders", params=params).data or []


def get_agencies():
    params = {"select": "*", "order": "tender_count.desc"}
    return get_read_client().select("agency_activity", params=params).data or []


def get_role_demand():
    params = {"select": "*", "order": "demand_count.desc"}
    return get_read_client().select("role_demand", params=params).data or []


def get_tech_trends():
    params = {"select": "*", "order": "mention_count.desc"}
    return get_read_client().select("tech_trends", params=params).data or []


def get_theme_summary():
    params = {"select": "*", "order": "mention_count.desc"}
    return get_read_client().select("theme_summary", params=params).data or []


def get_scrape_runs(limit: int = 10):
    params = {"select": "*", "order": "run_date.desc", "limit": str(limit)}
    return get_read_client().select("tender_scrape_runs", params=params).data or []


def get_overview_stats():
    client = get_read_client()
    all_t = client.select("tenders", params={"select": "id"}, count="exact")
    open_t = client.select(
        "tenders",
        params={"select": "id", "status": _eq("open")},
        count="exact",
    )
    high = client.select(
        "tenders",
        params={"select": "id", "relevance_score": _gte(70)},
        count="exact",
    )
    return {
        "total": all_t.count or 0,
        "open": open_t.count or 0,
        "high_relevance": high.count or 0,
    }


def get_distinct_agencies():
    rows = get_read_client().select("tenders", params={"select": "agency"}).data or []
    return sorted({row["agency"] for row in rows if row.get("agency")})


def get_distinct_categories():
    rows = get_read_client().select("tenders", params={"select": "category"}).data or []
    return sorted({row["category"] for row in rows if row.get("category")})


def tender_exists(gets_url: str) -> bool:
    result = get_write_client().select(
        "tenders",
        params={"select": "id", "gets_url": _eq(gets_url), "limit": "1"},
    )
    return len(result.data or []) > 0


def upsert_tender(data: dict):
    return get_write_client().upsert("tenders", data, on_conflict="gets_url")


def create_scrape_run() -> str:
    result = get_write_client().insert(
        "tender_scrape_runs",
        {"run_date": datetime.now(timezone.utc).isoformat()},
    )
    rows = result.data or []
    return rows[0]["id"]


def update_scrape_run(run_id: str, found: int, new: int, errors: str | None = None):
    get_write_client().update(
        "tender_scrape_runs",
        filters={"id": _eq(run_id)},
        payload={"tenders_found": found, "tenders_new": new, "errors": errors},
    )
