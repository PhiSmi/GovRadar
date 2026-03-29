from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.client import PostgrestError, get_read_client, get_write_client


def _filter_value(operator: str, value) -> str:
    return f"{operator}.{value}"


def _eq(value) -> str:
    return _filter_value("eq", value)


def _gte(value) -> str:
    return _filter_value("gte", value)


def _lte(value) -> str:
    return _filter_value("lte", value)


def _in(values: list[str]) -> str:
    quoted_items = []
    for value in values:
        escaped = str(value).replace('"', '\\"')
        quoted_items.append(f'"{escaped}"')
    quoted = ",".join(quoted_items)
    return f"in.({quoted})"


def _is_missing_column(error: Exception) -> bool:
    message = str(error)
    return "42703" in message or "does not exist" in message


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


def get_all_tenders(limit: int = 1000):
    params = {"select": "*", "order": "date_scraped.desc", "limit": str(limit)}
    return get_read_client().select("tenders", params=params).data or []


def get_recent_tenders(limit: int = 25, days: int = 30):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    client = get_read_client()
    try:
        params = {
            "select": "*",
            "order": "first_seen_at.desc,relevance_score.desc",
            "limit": str(limit),
            "first_seen_at": _gte(since.isoformat()),
        }
        return client.select("tenders", params=params).data or []
    except PostgrestError as error:
        if not _is_missing_column(error):
            raise

    fallback_params = {
        "select": "*",
        "order": "date_scraped.desc,relevance_score.desc",
        "limit": str(limit),
        "date_scraped": _gte(since.isoformat()),
    }
    return client.select("tenders", params=fallback_params).data or []


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


def get_latest_scrape_run():
    rows = get_scrape_runs(limit=1)
    return rows[0] if rows else None


def get_overview_stats():
    client = get_read_client()
    all_t = client.select("tenders", params={"select": "id"}, count="exact")
    open_t = client.select("tenders", params={"select": "id", "status": _eq("open")}, count="exact")
    high = client.select("tenders", params={"select": "id", "relevance_score": _gte(70)}, count="exact")
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        recent = client.select(
            "tenders",
            params={"select": "id", "first_seen_at": _gte(recent_cutoff.isoformat())},
            count="exact",
        )
    except PostgrestError as error:
        if not _is_missing_column(error):
            raise
        recent = client.select(
            "tenders",
            params={"select": "id", "date_scraped": _gte(recent_cutoff.isoformat())},
            count="exact",
        )
    return {
        "total": all_t.count or 0,
        "open": open_t.count or 0,
        "high_relevance": high.count or 0,
        "recent_new": recent.count or 0,
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


def get_existing_tender_urls(gets_urls: list[str], batch_size: int = 25) -> set[str]:
    if not gets_urls:
        return set()

    existing: set[str] = set()
    client = get_write_client()

    for start in range(0, len(gets_urls), batch_size):
        batch = gets_urls[start : start + batch_size]
        rows = client.select(
            "tenders",
            params={
                "select": "gets_url",
                "gets_url": _in(batch),
                "limit": str(len(batch)),
            },
        ).data or []
        existing.update(row["gets_url"] for row in rows if row.get("gets_url"))

    return existing


def upsert_tender(data: dict):
    return get_write_client().upsert("tenders", data, on_conflict="gets_url")


def create_scrape_run() -> str:
    result = get_write_client().insert(
        "tender_scrape_runs",
        {"run_date": datetime.now(timezone.utc).isoformat()},
    )
    rows = result.data or []
    return rows[0]["id"]


def update_scrape_run(
    run_id: str,
    found: int,
    new: int,
    high_relevance: int,
    closing_soon: int,
    summary: str,
    errors: str | None = None,
):
    get_write_client().update(
        "tender_scrape_runs",
        filters={"id": _eq(run_id)},
        payload={
            "tenders_found": found,
            "tenders_new": new,
            "high_relevance_found": high_relevance,
            "closing_soon_count": closing_soon,
            "summary": summary,
            "errors": errors,
        },
    )
