from __future__ import annotations
from datetime import datetime
from db.client import get_client


# ── Reads ─────────────────────────────────────────────────────────────

def get_tenders(
    status: str | None = None,
    min_relevance: int = 0,
    agency: str | None = None,
    category: str | None = None,
    limit: int = 200,
):
    q = get_client().table("tenders").select("*")
    if status:
        q = q.eq("status", status)
    if min_relevance > 0:
        q = q.gte("relevance_score", min_relevance)
    if agency:
        q = q.eq("agency", agency)
    if category:
        q = q.eq("category", category)
    return q.order("relevance_score", desc=True).limit(limit).execute().data


def get_agencies():
    return (
        get_client()
        .table("agency_activity")
        .select("*")
        .execute()
        .data
    )


def get_role_demand():
    return (
        get_client()
        .table("role_demand")
        .select("*")
        .execute()
        .data
    )


def get_tech_trends():
    return (
        get_client()
        .table("tech_trends")
        .select("*")
        .execute()
        .data
    )


def get_theme_summary():
    return (
        get_client()
        .table("theme_summary")
        .select("*")
        .execute()
        .data
    )


def get_scrape_runs(limit: int = 10):
    return (
        get_client()
        .table("tender_scrape_runs")
        .select("*")
        .order("run_date", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def get_overview_stats():
    client = get_client()
    all_t = client.table("tenders").select("id", count="exact").execute()
    open_t = (
        client.table("tenders")
        .select("id", count="exact")
        .eq("status", "open")
        .execute()
    )
    high = (
        client.table("tenders")
        .select("id", count="exact")
        .gte("relevance_score", 70)
        .execute()
    )
    return {
        "total": all_t.count or 0,
        "open": open_t.count or 0,
        "high_relevance": high.count or 0,
    }


def get_distinct_agencies():
    rows = (
        get_client()
        .table("tenders")
        .select("agency")
        .execute()
        .data
    )
    return sorted({r["agency"] for r in rows if r.get("agency")})


def get_distinct_categories():
    rows = (
        get_client()
        .table("tenders")
        .select("category")
        .execute()
        .data
    )
    return sorted({r["category"] for r in rows if r.get("category")})


# ── Writes ────────────────────────────────────────────────────────────

def tender_exists(gets_url: str) -> bool:
    res = (
        get_client()
        .table("tenders")
        .select("id")
        .eq("gets_url", gets_url)
        .execute()
    )
    return len(res.data) > 0


def upsert_tender(data: dict):
    return (
        get_client()
        .table("tenders")
        .upsert(data, on_conflict="gets_url")
        .execute()
    )


def create_scrape_run() -> str:
    res = (
        get_client()
        .table("tender_scrape_runs")
        .insert({"run_date": datetime.utcnow().isoformat()})
        .execute()
    )
    return res.data[0]["id"]


def update_scrape_run(run_id: str, found: int, new: int, errors: str | None = None):
    get_client().table("tender_scrape_runs").update(
        {"tenders_found": found, "tenders_new": new, "errors": errors}
    ).eq("id", run_id).execute()
