"""GovRadar Streamlit dashboard."""

from __future__ import annotations

import os
from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st


def _secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


# Streamlit Cloud secrets first; local .env loading happens in db.client.
os.environ.setdefault("SUPABASE_URL", _secret("SUPABASE_URL", ""))
os.environ.setdefault(
    "SUPABASE_ANON_KEY",
    _secret("SUPABASE_ANON_KEY", _secret("SUPABASE_KEY", "")),
)
os.environ.setdefault(
    "SUPABASE_PUBLISHABLE_KEY",
    _secret("SUPABASE_PUBLISHABLE_KEY", _secret("SUPABASE_KEY", "")),
)
os.environ.setdefault("SUPABASE_KEY", _secret("SUPABASE_KEY", ""))
os.environ.setdefault(
    "SUPABASE_SERVICE_ROLE_KEY",
    _secret("SUPABASE_SERVICE_ROLE_KEY", ""),
)

from db.queries import (
    get_agencies,
    get_all_tenders,
    get_distinct_agencies,
    get_distinct_categories,
    get_latest_scrape_run,
    get_overview_stats,
    get_recent_tenders,
    get_role_demand,
    get_scrape_runs,
    get_tenders,
    get_tech_trends,
    get_theme_summary,
)


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(147, 197, 253, 0.32), transparent 28%),
                    radial-gradient(circle at top right, rgba(94, 234, 212, 0.18), transparent 24%),
                    linear-gradient(180deg, #f6fbff 0%, #f2f6fb 55%, #edf3f8 100%);
            }
            .block-container {
                max-width: 1420px;
                padding-top: 1.8rem;
                padding-bottom: 2.4rem;
            }
            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #f8fbff 0%, #eef5fb 100%);
                border-right: 1px solid #d7e2eb;
            }
            div[data-testid="stMetric"] {
                background: rgba(255, 255, 255, 0.92);
                border: 1px solid #dbe5ee;
                border-radius: 20px;
                padding: 0.8rem 1rem;
                box-shadow: 0 20px 60px rgba(15, 23, 42, 0.06);
            }
            div[data-testid="stDataFrame"] {
                border-radius: 22px;
                overflow: hidden;
                border: 1px solid #dbe5ee;
                box-shadow: 0 24px 64px rgba(15, 23, 42, 0.07);
            }
            .hero {
                background: linear-gradient(135deg, #082f49 0%, #0f3f63 42%, #0f766e 100%);
                border: 1px solid rgba(255, 255, 255, 0.10);
                color: #f8fafc;
                border-radius: 28px;
                padding: 1.6rem 1.8rem;
                box-shadow: 0 30px 80px rgba(8, 47, 73, 0.28);
                margin-bottom: 1rem;
            }
            .hero-kicker {
                font-size: 0.78rem;
                text-transform: uppercase;
                letter-spacing: 0.14em;
                opacity: 0.76;
                margin-bottom: 0.55rem;
            }
            .hero-title {
                font-size: 2rem;
                font-weight: 700;
                line-height: 1.1;
                margin-bottom: 0.55rem;
            }
            .hero-copy {
                max-width: 58rem;
                opacity: 0.9;
                font-size: 0.98rem;
                line-height: 1.5;
            }
            .hero-meta {
                display: inline-block;
                margin-top: 0.9rem;
                padding: 0.3rem 0.65rem;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.12);
                font-size: 0.82rem;
            }
            .surface {
                background: rgba(255, 255, 255, 0.88);
                border: 1px solid #dbe5ee;
                border-radius: 22px;
                padding: 1rem 1.1rem;
                box-shadow: 0 18px 48px rgba(15, 23, 42, 0.05);
            }
            .surface h4 {
                margin: 0 0 0.4rem 0;
                font-size: 1rem;
            }
            .surface p {
                margin: 0;
                color: #475569;
                line-height: 1.45;
            }
            .spotlight {
                background: rgba(255, 255, 255, 0.88);
                border: 1px solid #d8e4ec;
                border-radius: 22px;
                padding: 1rem 1.05rem;
                margin-bottom: 0.9rem;
                box-shadow: 0 18px 48px rgba(15, 23, 42, 0.05);
            }
            .spotlight-top {
                display: flex;
                justify-content: space-between;
                gap: 0.8rem;
                margin-bottom: 0.4rem;
                align-items: flex-start;
            }
            .spotlight-title {
                font-size: 1rem;
                font-weight: 650;
                color: #0f172a;
                margin: 0;
            }
            .spotlight-meta {
                color: #475569;
                font-size: 0.88rem;
                margin-bottom: 0.65rem;
            }
            .badge {
                display: inline-block;
                padding: 0.28rem 0.62rem;
                border-radius: 999px;
                font-size: 0.76rem;
                font-weight: 650;
                white-space: nowrap;
            }
            .badge-open {
                background: #dcfce7;
                color: #166534;
            }
            .badge-closed {
                background: #fee2e2;
                color: #991b1b;
            }
            .badge-new {
                background: #fef3c7;
                color: #92400e;
            }
            .badge-score {
                background: #dbeafe;
                color: #1d4ed8;
            }
            .chip-row {
                margin-top: 0.6rem;
            }
            .chip {
                display: inline-block;
                margin: 0 0.45rem 0.45rem 0;
                padding: 0.26rem 0.58rem;
                background: #eff6ff;
                border: 1px solid #dbeafe;
                color: #1e3a8a;
                border-radius: 999px;
                font-size: 0.76rem;
            }
            .minor-note {
                font-size: 0.84rem;
                color: #475569;
            }
            .callout, .admin-box {
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid #dbe5ee;
                border-radius: 22px;
                box-shadow: 0 18px 48px rgba(15, 23, 42, 0.05);
            }
            .callout {
                padding: 1rem 1.1rem;
                margin-bottom: 1rem;
            }
            .admin-box {
                padding: 1rem 1.05rem;
                margin-bottom: 1rem;
            }
            .callout h4, .admin-box h4 {
                margin: 0 0 0.45rem 0;
                font-size: 1rem;
            }
            .callout p, .admin-box p {
                margin: 0.2rem 0;
                color: #475569;
                line-height: 1.45;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_data_error(error: Exception) -> str:
    message = str(error)

    if "PGRST205" in message and "public.tenders" in message:
        return (
            "Supabase is reachable, but the GovRadar schema is missing in the connected "
            "project. Run setup/schema.sql in Supabase, then run the scraper once with "
            "a write-capable key."
        )

    if "SUPABASE_URL must be set" in message or "Supabase read key must be set" in message:
        return (
            "Supabase credentials are missing. Set SUPABASE_URL plus a read key such as "
            "SUPABASE_ANON_KEY, SUPABASE_PUBLISHABLE_KEY, or SUPABASE_KEY."
        )

    return f"Could not load tenders: {error}"


def _normalise_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    clean = df.copy()
    for column in ["probable_tech_stack", "probable_roles", "themes", "attachment_urls"]:
        if column in clean.columns:
            clean[column] = clean[column].apply(
                lambda value: value if isinstance(value, list) else ([] if value in (None, "") else [str(value)])
            )

    if "relevance_score" in clean.columns:
        clean["relevance_score"] = pd.to_numeric(clean["relevance_score"], errors="coerce").fillna(0).astype(int)

    if "closing_date" in clean.columns:
        clean["closing_date"] = pd.to_datetime(clean["closing_date"], errors="coerce").dt.date

    for column in ["date_scraped", "first_seen_at", "last_seen_at", "enrichment_updated_at"]:
        if column in clean.columns:
            clean[column] = pd.to_datetime(clean[column], utc=True, errors="coerce")

    for column in [
        "title",
        "agency",
        "category",
        "description",
        "tender_type",
        "estimated_value",
        "programme_size",
        "relevance_reasoning",
        "estimated_seek_timeline",
        "status",
        "gets_url",
        "attachment_text_excerpt",
        "rfx_id",
        "summary",
        "errors",
        "enrichment_model",
        "enrichment_prompt_version",
    ]:
        if column in clean.columns:
            clean[column] = clean[column].fillna("")

    return clean


def _match_search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if df.empty or not query.strip():
        return df

    needle = query.strip().lower()
    mask = pd.Series(False, index=df.index)

    for column in ["title", "agency", "category", "description", "tender_type", "relevance_reasoning"]:
        if column in df.columns:
            mask = mask | df[column].astype(str).str.lower().str.contains(needle, na=False)

    for column in ["probable_tech_stack", "probable_roles", "themes"]:
        if column in df.columns:
            mask = mask | df[column].apply(
                lambda items: needle in " ".join(str(item).lower() for item in items)
            )

    return df[mask]


def _sort_frame(df: pd.DataFrame, sort_mode: str) -> pd.DataFrame:
    if df.empty:
        return df

    if sort_mode == "Closing soon":
        return df.sort_values(
            by=["closing_date", "relevance_score"],
            ascending=[True, False],
            na_position="last",
        )
    if sort_mode == "Newest discovered":
        return df.sort_values(by=["first_seen_at", "relevance_score"], ascending=[False, False], na_position="last")
    if sort_mode == "Newest scrape":
        return df.sort_values(by=["date_scraped", "relevance_score"], ascending=[False, False], na_position="last")
    if sort_mode == "Agency":
        return df.sort_values(by=["agency", "relevance_score"], ascending=[True, False], na_position="last")
    return df.sort_values(by=["relevance_score", "closing_date"], ascending=[False, True], na_position="last")


def _chip_markup(items: list[str]) -> str:
    chips = "".join(f"<span class='chip'>{escape(str(item))}</span>" for item in items if str(item).strip())
    return f"<div class='chip-row'>{chips}</div>" if chips else ""


def _latest_run_timestamp(run: dict | None):
    if not run:
        return None
    raw_date = run.get("run_date", "")
    return pd.to_datetime(raw_date, utc=True, errors="coerce")


def _is_new_tender(row: pd.Series, latest_run_ts) -> bool:
    if latest_run_ts is None:
        return False
    first_seen = row.get("first_seen_at")
    return pd.notna(first_seen) and first_seen >= latest_run_ts


def _run_summary(run: dict | None) -> tuple[str, str]:
    if not run:
        return "No scrape run recorded yet", "Connect a write-capable key and run the scraper once."

    raw_date = run.get("run_date", "")
    try:
        stamp = pd.to_datetime(raw_date, utc=True)
        when = stamp.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        when = raw_date or "unknown"

    found = run.get("tenders_found", 0)
    created = run.get("tenders_new", 0)
    return f"Last scrape: {when}", f"{found} tenders processed, {created} new."


def _apply_preset(df: pd.DataFrame, preset: str, latest_run_ts) -> pd.DataFrame:
    if df.empty or preset == "Custom":
        return df

    today = date.today()
    closing_cutoff = today + timedelta(days=21)
    work = df.copy()

    if preset == "High Relevance":
        return work[(work["relevance_score"] >= 70) & (work["status"] == "open")]
    if preset == "Closing Soon":
        return work[
            (work["status"] == "open")
            & work["closing_date"].notna()
            & (work["closing_date"] >= today)
            & (work["closing_date"] <= closing_cutoff)
        ]
    if preset == "Health Focus":
        mask = work["agency"].str.contains("health|te whatu", case=False, na=False)
        mask = mask | work["description"].str.contains("health|hospital|clinical|patient|te whatu", case=False, na=False)
        return work[mask]
    if preset == "Integration & APIs":
        mask = work["title"].str.contains("integration|api", case=False, na=False)
        mask = mask | work["description"].str.contains("integration|api|interface|middleware|fhir|hl7", case=False, na=False)
        return work[mask]
    if preset == "New This Run":
        if latest_run_ts is None:
            return work.iloc[0:0]
        return work[work["first_seen_at"].notna() & (work["first_seen_at"] >= latest_run_ts)]
    return work


def _credential_mode() -> str:
    has_service = bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip())
    has_public = bool(
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if has_service and not has_public:
        return "Private dashboard mode"
    if has_service and has_public:
        return "Mixed mode"
    if has_public:
        return "Public-read mode"
    return "Unknown"


def _health_snapshot(df: pd.DataFrame, latest_run: dict | None) -> dict:
    if df.empty:
        return {
            "enrichment_failed": 0,
            "missing_category": 0,
            "missing_agency": 0,
            "attachment_backed": 0,
            "stale_open": 0,
            "mode": _credential_mode(),
            "last_run_errors": latest_run.get("errors", "") if latest_run else "",
        }

    stale_open = 0
    if "closing_date" in df.columns:
        stale_open = len(
            df[
                (df["status"] == "open")
                & df["closing_date"].notna()
                & (df["closing_date"] < date.today())
            ]
        )

    return {
        "enrichment_failed": len(df[df["relevance_reasoning"].str.contains("Enrichment failed", case=False, na=False)]),
        "missing_category": len(df[df["category"].eq("")]),
        "missing_agency": len(df[df["agency"].eq("")]),
        "attachment_backed": len(df[df["attachment_text_excerpt"].astype(str).str.len() > 0]),
        "stale_open": stale_open,
        "mode": _credential_mode(),
        "last_run_errors": latest_run.get("errors", "") if latest_run else "",
    }


def _render_onboarding() -> None:
    st.markdown(
        """
        <div class="callout">
            <h4>First run setup</h4>
            <p>The dashboard is connected, but there is no scrape data yet.</p>
            <p>1. Run <code>setup/schema.sql</code> in Supabase.</p>
            <p>2. If you want the dashboard private, run <code>setup/private_dashboard.sql</code>.</p>
            <p>3. Configure <code>SUPABASE_SERVICE_ROLE_KEY</code> and <code>ANTHROPIC_API_KEY</code>.</p>
            <p>4. Run <code>python -m scraper.run</code> once, or trigger the GitHub workflow manually.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_spotlight(row: pd.Series, latest_run_ts) -> None:
    status = str(row.get("status", "")).lower()
    badge_class = "badge-open" if status == "open" else "badge-closed"
    title = escape(str(row.get("title", "")))
    agency = escape(str(row.get("agency", "")))
    closing = row.get("closing_date") or "TBC"
    reason = escape(str(row.get("relevance_reasoning", "")))
    tech = row.get("probable_tech_stack", [])
    timeline = escape(str(row.get("estimated_seek_timeline", "")))
    score = int(row.get("relevance_score", 0) or 0)
    url = row.get("gets_url", "")
    new_badge = "<span class='badge badge-new'>new</span>" if _is_new_tender(row, latest_run_ts) else ""

    st.markdown(
        f"""
        <div class="spotlight">
            <div class="spotlight-top">
                <div class="spotlight-title">{title}</div>
                <div>
                    <span class="badge {badge_class}">{escape(status or 'unknown')}</span>
                    <span class="badge badge-score">{score}</span>
                    {new_badge}
                </div>
            </div>
            <div class="spotlight-meta">{agency} | closes {closing} | expected hiring {timeline or 'unspecified'}</div>
            <div class="minor-note">{reason or 'No relevance rationale recorded yet.'}</div>
            {_chip_markup(tech[:6])}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if url:
        st.markdown(f"[Open tender]({url})")


@st.cache_data(ttl=300, show_spinner=False)
def load_filter_options():
    return get_distinct_agencies(), get_distinct_categories()


@st.cache_data(ttl=300, show_spinner=False)
def load_tenders(status, min_relevance, agency, category):
    return get_tenders(
        status=status,
        min_relevance=min_relevance,
        agency=agency,
        category=category,
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_all_tenders():
    return get_all_tenders()


@st.cache_data(ttl=300, show_spinner=False)
def load_recent_tenders():
    return get_recent_tenders(limit=30, days=45)


@st.cache_data(ttl=300, show_spinner=False)
def load_overview_stats():
    return get_overview_stats()


@st.cache_data(ttl=300, show_spinner=False)
def load_agency_data():
    return get_agencies()


@st.cache_data(ttl=300, show_spinner=False)
def load_tech_data():
    return get_tech_trends()


@st.cache_data(ttl=300, show_spinner=False)
def load_role_data():
    return get_role_demand()


@st.cache_data(ttl=300, show_spinner=False)
def load_theme_data():
    return get_theme_summary()


@st.cache_data(ttl=300, show_spinner=False)
def load_scrape_history(limit: int = 5):
    return get_scrape_runs(limit=limit)


@st.cache_data(ttl=300, show_spinner=False)
def load_latest_run():
    return get_latest_scrape_run()


st.set_page_config(page_title="GovRadar", layout="wide")
_inject_styles()

latest_run: dict | None = None
runs: list[dict] = []
all_df = pd.DataFrame()
recent_df = pd.DataFrame()
load_error: Exception | None = None
try:
    latest_run = load_latest_run()
except Exception as error:
    load_error = error

try:
    runs = load_scrape_history(limit=5)
except Exception as error:
    load_error = load_error or error
    runs = []

try:
    all_df = _normalise_frame(pd.DataFrame(load_all_tenders()))
except Exception as error:
    load_error = load_error or error
    all_df = pd.DataFrame()

try:
    recent_df = _normalise_frame(pd.DataFrame(load_recent_tenders()))
except Exception as error:
    load_error = load_error or error
    recent_df = pd.DataFrame()

headline, run_note = _run_summary(latest_run)
latest_run_ts = _latest_run_timestamp(latest_run)

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-kicker">Government delivery intelligence</div>
        <div class="hero-title">GovRadar</div>
        <div class="hero-copy">
            Track where New Zealand government technology work is forming before it shows up as downstream hiring.
            Review live GETS opportunities, rank them against a contractor profile, and scan the market by agency,
            stack, role demand, and expected delivery timing.
        </div>
        <div class="hero-meta">{escape(headline)} | {escape(run_note)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.header("Filters")
preset = st.sidebar.selectbox(
    "Preset view",
    ["Custom", "High Relevance", "Closing Soon", "Health Focus", "Integration & APIs", "New This Run"],
)
search_query = st.sidebar.text_input("Search tenders", placeholder="Agency, technology, role, keyword")
status_filter = st.sidebar.selectbox("Status", ["All", "open", "closed"])
min_relevance = st.sidebar.slider("Min relevance score", 0, 100, 40, 5)
high_priority_only = st.sidebar.toggle("Only show 70+ opportunities", value=False)
sort_mode = st.sidebar.selectbox(
    "Sort by",
    ["Highest relevance", "Closing soon", "Newest discovered", "Newest scrape", "Agency"],
)

distinct_agencies: list[str] = []
distinct_categories: list[str] = []
if not all_df.empty:
    distinct_agencies = sorted(all_df["agency"].replace("", pd.NA).dropna().astype(str).unique().tolist())
    distinct_categories = sorted(all_df["category"].replace("", pd.NA).dropna().astype(str).unique().tolist())
else:
    try:
        distinct_agencies, distinct_categories = load_filter_options()
    except Exception:
        pass

agency_filter = st.sidebar.selectbox("Agency", ["All"] + distinct_agencies)
category_filter = st.sidebar.selectbox("Category", ["All"] + distinct_categories)

if load_error:
    st.error(_format_data_error(load_error))

df = all_df.copy()
if not df.empty:
    if status_filter != "All" and "status" in df.columns:
        df = df[df["status"] == status_filter]
    if min_relevance > 0 and "relevance_score" in df.columns:
        df = df[df["relevance_score"] >= min_relevance]
    if agency_filter != "All" and "agency" in df.columns:
        df = df[df["agency"] == agency_filter]
    if category_filter != "All" and "category" in df.columns:
        df = df[df["category"] == category_filter]

filtered_df = _apply_preset(df, preset, latest_run_ts)
filtered_df = _match_search(filtered_df, search_query)
if high_priority_only and not filtered_df.empty and "relevance_score" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["relevance_score"] >= 70]
filtered_df = _sort_frame(filtered_df, sort_mode)

try:
    stats = load_overview_stats()
except Exception:
    stats = {"total": 0, "open": 0, "high_relevance": 0, "recent_new": 0}

open_df = filtered_df[filtered_df["status"].eq("open")] if "status" in filtered_df.columns else filtered_df
today = date.today()
closing_cutoff = today + timedelta(days=21)
closing_soon_df = (
    open_df[
        open_df["closing_date"].notna()
        & (open_df["closing_date"] >= today)
        & (open_df["closing_date"] <= closing_cutoff)
    ]
    if not open_df.empty and "closing_date" in open_df.columns
    else pd.DataFrame()
)
avg_relevance = int(filtered_df["relevance_score"].mean()) if not filtered_df.empty else 0
new_this_run_df = (
    all_df[all_df["first_seen_at"].notna() & (all_df["first_seen_at"] >= latest_run_ts)]
    if latest_run_ts is not None and not all_df.empty
    else pd.DataFrame()
)

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Tracked tenders", stats["total"])
col2.metric("Open tenders", stats["open"])
col3.metric("High relevance", stats["high_relevance"])
col4.metric("New in 7 days", stats["recent_new"])
col5.metric("Closing in 21 days", len(closing_soon_df))
col6.metric("Average relevance", avg_relevance)

with st.sidebar:
    st.divider()
    st.subheader("Current view")
    st.caption(f"{len(filtered_df)} tenders after filters")
    st.caption(f"Preset: {preset}")
    if not filtered_df.empty and "gets_url" in filtered_df.columns:
        csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export filtered CSV",
            data=csv_bytes,
            file_name="govradar-filtered-tenders.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()
    st.subheader("Scrape history")
    if runs:
        for run in runs:
            run_date = run.get("run_date", "")[:10]
            found = run.get("tenders_found", 0)
            created = run.get("tenders_new", 0)
            st.caption(f"{run_date}: {found} processed, {created} new")
    else:
        st.caption("No scrape runs recorded yet.")

tab_overview, tab_recent, tab_pipeline, tab_agencies, tab_tech, tab_roles, tab_timeline, tab_themes, tab_admin = st.tabs(
    ["Overview", "Recent Changes", "Pipeline", "Agencies", "Tech", "Roles", "Timeline", "Themes", "Admin"]
)

with tab_overview:
    if all_df.empty:
        _render_onboarding()
    elif filtered_df.empty:
        st.info("No tenders match the current filters.")
    else:
        left, right = st.columns([1.35, 1.0], gap="large")

        with left:
            st.subheader("Opportunity spotlight")
            spotlight = filtered_df.head(6)
            for _, row in spotlight.iterrows():
                _render_spotlight(row, latest_run_ts)

        with right:
            top_agency = ""
            if "agency" in open_df.columns and not open_df.empty:
                agency_counts = open_df["agency"].replace("", pd.NA).dropna().value_counts()
                if not agency_counts.empty:
                    top_agency = str(agency_counts.index[0])

            top_timeline = ""
            if "estimated_seek_timeline" in filtered_df.columns and not filtered_df.empty:
                timeline_counts = filtered_df["estimated_seek_timeline"].replace("", pd.NA).dropna().value_counts()
                if not timeline_counts.empty:
                    top_timeline = str(timeline_counts.index[0])

            st.markdown(
                f"""
                <div class="surface">
                    <h4>Market read</h4>
                    <p>Dominant agency in the filtered set: <strong>{escape(top_agency or 'None yet')}</strong></p>
                    <p>Most common hiring window: <strong>{escape(top_timeline or 'Unspecified')}</strong></p>
                    <p>New tenders in the latest run: <strong>{len(new_this_run_df)}</strong></p>
                    <p>Search is applied across title, agency, category, description, and enrichment fields.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.write("")
            st.subheader("Closings soon")
            if closing_soon_df.empty:
                st.caption("No open tenders close in the next 21 days.")
            else:
                st.dataframe(
                    closing_soon_df[["title", "agency", "closing_date", "relevance_score"]].head(10),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "closing_date": st.column_config.DateColumn("Closes", format="YYYY-MM-DD"),
                        "relevance_score": st.column_config.ProgressColumn(
                            "Relevance",
                            min_value=0,
                            max_value=100,
                            format="%d",
                        ),
                    },
                )

        lower_left, lower_right = st.columns(2, gap="large")
        with lower_left:
            st.subheader("Expected hiring windows")
            if "estimated_seek_timeline" in filtered_df.columns and not filtered_df.empty:
                timeline_chart = (
                    filtered_df["estimated_seek_timeline"]
                    .replace("", pd.NA)
                    .dropna()
                    .value_counts()
                    .reindex(["3 months", "6 months", "9 months", "12 months"])
                    .fillna(0)
                )
                if timeline_chart.sum() > 0:
                    st.bar_chart(timeline_chart)
                else:
                    st.caption("Timeline enrichment has not been populated yet.")
            else:
                st.caption("Timeline enrichment has not been populated yet.")

        with lower_right:
            st.subheader("Relevance distribution")
            if not filtered_df.empty and "relevance_score" in filtered_df.columns:
                score_bands = pd.cut(
                    filtered_df["relevance_score"],
                    bins=[-1, 39, 69, 84, 100],
                    labels=["0-39", "40-69", "70-84", "85-100"],
                ).value_counts().sort_index()
                st.bar_chart(score_bands)
            else:
                st.caption("No relevance data available.")

with tab_recent:
    if all_df.empty:
        _render_onboarding()
    else:
        st.subheader("New this run")
        if new_this_run_df.empty:
            st.caption("No newly discovered tenders are available for the latest run yet.")
        else:
            recent_new = _sort_frame(new_this_run_df, "Highest relevance")
            st.dataframe(
                recent_new[["title", "agency", "relevance_score", "closing_date", "status"]].head(20),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "closing_date": st.column_config.DateColumn("Closes", format="YYYY-MM-DD"),
                    "relevance_score": st.column_config.ProgressColumn(
                        "Relevance",
                        min_value=0,
                        max_value=100,
                        format="%d",
                    ),
                },
            )

        st.subheader("Recently discovered tenders")
        if recent_df.empty:
            st.caption("No recent tender history available yet.")
        else:
            st.dataframe(
                recent_df[["title", "agency", "first_seen_at", "relevance_score", "status"]].head(25),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "first_seen_at": st.column_config.DatetimeColumn("First seen", format="YYYY-MM-DD HH:mm"),
                    "relevance_score": st.column_config.ProgressColumn(
                        "Relevance",
                        min_value=0,
                        max_value=100,
                        format="%d",
                    ),
                },
            )

        if latest_run and latest_run.get("summary"):
            st.subheader("Latest run summary")
            st.markdown(latest_run["summary"])

with tab_pipeline:
    if all_df.empty:
        _render_onboarding()
    elif filtered_df.empty:
        st.info("No tenders match the current filters.")
    else:
        st.subheader("Tender explorer")
        explorer_df = filtered_df.copy()
        explorer_df["attachment_count"] = explorer_df["attachment_urls"].apply(len) if "attachment_urls" in explorer_df.columns else 0
        display_cols = [
            "title",
            "agency",
            "rfx_id",
            "category",
            "tender_type",
            "closing_date",
            "relevance_score",
            "programme_size",
            "estimated_seek_timeline",
            "status",
            "first_seen_at",
            "attachment_count",
            "gets_url",
        ]
        available = [column for column in display_cols if column in explorer_df.columns]
        st.dataframe(
            explorer_df[available],
            hide_index=True,
            use_container_width=True,
            column_config={
                "closing_date": st.column_config.DateColumn("Closes", format="YYYY-MM-DD"),
                "first_seen_at": st.column_config.DatetimeColumn("First seen", format="YYYY-MM-DD HH:mm"),
                "relevance_score": st.column_config.ProgressColumn(
                    "Relevance",
                    min_value=0,
                    max_value=100,
                    format="%d",
                ),
                "attachment_count": st.column_config.NumberColumn("Attachments", format="%d"),
                "gets_url": st.column_config.LinkColumn("GETS listing"),
            },
        )

        st.subheader("Tender details")
        for _, row in filtered_df.head(12).iterrows():
            title = row.get("title", "")
            agency = row.get("agency", "")
            relevance = row.get("relevance_score", 0)
            prefix = "NEW | " if _is_new_tender(row, latest_run_ts) else ""
            with st.expander(f"{prefix}{title} | {agency} | relevance {relevance}"):
                a, b, c = st.columns(3)
                a.write(f"**Tender type:** {row.get('tender_type', '-') or '-'}")
                a.write(f"**RFX ID:** {row.get('rfx_id', '-') or '-'}")
                a.write(f"**Closing date:** {row.get('closing_date', '-') or '-'}")
                a.write(f"**Estimated value:** {row.get('estimated_value', '-') or '-'}")
                a.write(f"**First seen:** {row.get('first_seen_at', '-') or '-'}")

                b.write(f"**Status:** {row.get('status', '-') or '-'}")
                b.write(f"**Category:** {row.get('category', '-') or '-'}")
                b.write(f"**Expected hiring window:** {row.get('estimated_seek_timeline', '-') or '-'}")
                b.write(f"**Relevance score:** {relevance}/100")

                c.write(f"**Programme size:** {row.get('programme_size', '-') or '-'}")
                c.write(f"**Last seen:** {row.get('last_seen_at', '-') or '-'}")
                c.write(f"**Attachments:** {len(row.get('attachment_urls', []))}")
                c.write(f"**Model / prompt:** {row.get('enrichment_model', '-') or '-'} / {row.get('enrichment_prompt_version', '-') or '-'}")

                st.write(f"**Why it matters:** {row.get('relevance_reasoning', '-') or '-'}")

                tech = row.get("probable_tech_stack", [])
                if tech:
                    st.write(f"**Likely tech stack:** {', '.join(tech)}")

                roles = row.get("probable_roles", [])
                if roles:
                    st.write(f"**Likely roles:** {', '.join(roles)}")

                themes = row.get("themes", [])
                if themes:
                    st.write(f"**Themes:** {', '.join(themes)}")

                description = row.get("description", "")
                if description:
                    st.write("**Tender description**")
                    st.caption(description[:1800] + ("..." if len(description) > 1800 else ""))

                attachment_excerpt = row.get("attachment_text_excerpt", "")
                if attachment_excerpt:
                    st.write("**Attachment excerpt**")
                    st.caption(attachment_excerpt[:1200] + ("..." if len(attachment_excerpt) > 1200 else ""))

                attachment_urls = row.get("attachment_urls", [])
                if attachment_urls:
                    st.write("**Attachments**")
                    for attachment_url in attachment_urls[:6]:
                        st.markdown(f"- [Attachment]({attachment_url})")

                url = row.get("gets_url", "")
                if url:
                    st.markdown(f"[Open in GETS]({url})")

with tab_agencies:
    try:
        agency_data = pd.DataFrame(load_agency_data())
        if all_df.empty:
            _render_onboarding()
        elif agency_data.empty:
            st.info("No agency data available yet.")
        else:
            st.subheader("Agency activity")
            chart = agency_data.head(15).set_index("agency")["tender_count"]
            st.bar_chart(chart)
            st.dataframe(
                agency_data,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "avg_relevance": st.column_config.NumberColumn("Avg relevance", format="%.1f"),
                },
            )
    except Exception as error:
        st.error(f"Could not load agency data: {error}")

with tab_tech:
    try:
        tech_data = pd.DataFrame(load_tech_data())
        if all_df.empty:
            _render_onboarding()
        elif tech_data.empty:
            st.info("No tech trend data available yet.")
        else:
            st.subheader("Technology signals")
            st.bar_chart(tech_data.head(20).set_index("technology")["mention_count"])
            st.dataframe(tech_data, hide_index=True, use_container_width=True)
    except Exception as error:
        st.error(f"Could not load tech trend data: {error}")

with tab_roles:
    try:
        role_data = pd.DataFrame(load_role_data())
        if all_df.empty:
            _render_onboarding()
        elif role_data.empty:
            st.info("No role-demand data available yet.")
        else:
            st.subheader("Role demand")
            st.bar_chart(role_data.head(20).set_index("role")["demand_count"])
            st.dataframe(
                role_data,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "avg_relevance": st.column_config.NumberColumn("Avg relevance", format="%.1f"),
                },
            )
    except Exception as error:
        st.error(f"Could not load role demand: {error}")

with tab_timeline:
    if all_df.empty:
        _render_onboarding()
    elif filtered_df.empty or "estimated_seek_timeline" not in filtered_df.columns:
        st.info("No timeline data available.")
    else:
        st.subheader("Expected downstream hiring")
        timeline_counts = (
            filtered_df["estimated_seek_timeline"]
            .replace("", pd.NA)
            .dropna()
            .value_counts()
            .reindex(["3 months", "6 months", "9 months", "12 months"])
            .fillna(0)
        )
        if timeline_counts.sum() == 0:
            st.info("Timeline enrichment has not been populated yet.")
        else:
            st.bar_chart(timeline_counts)
            for period in ["3 months", "6 months", "9 months", "12 months"]:
                subset = filtered_df[filtered_df["estimated_seek_timeline"] == period]
                if not subset.empty:
                    st.write(f"**{period}**")
                    st.dataframe(
                        subset[["title", "agency", "relevance_score", "status"]].head(10),
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "relevance_score": st.column_config.ProgressColumn(
                                "Relevance",
                                min_value=0,
                                max_value=100,
                                format="%d",
                            ),
                        },
                    )

with tab_themes:
    try:
        theme_data = pd.DataFrame(load_theme_data())
        if all_df.empty:
            _render_onboarding()
        elif theme_data.empty:
            st.info("No theme data available yet.")
        else:
            st.subheader("Project themes")
            st.bar_chart(theme_data.head(20).set_index("theme")["mention_count"])
            st.dataframe(theme_data, hide_index=True, use_container_width=True)
    except Exception as error:
        st.error(f"Could not load theme data: {error}")

with tab_admin:
    st.subheader("Operational health")
    health = _health_snapshot(all_df, latest_run)

    a, b, c, d, e, f = st.columns(6)
    a.metric("Credential mode", health["mode"])
    b.metric("Attachment-backed", health["attachment_backed"])
    c.metric("Stale open", health["stale_open"])
    d.metric("Missing agency", health["missing_agency"])
    e.metric("Missing category", health["missing_category"])
    f.metric("Enrichment failed", health["enrichment_failed"])

    st.markdown(
        f"""
        <div class="admin-box">
            <h4>Runtime</h4>
            <p><strong>Latest run:</strong> {escape(headline)}</p>
            <p><strong>Run note:</strong> {escape(run_note)}</p>
            <p><strong>Total tenders loaded:</strong> {len(all_df)}</p>
            <p><strong>Recent tenders tracked:</strong> {len(recent_df)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not all_df.empty:
        latest_model = next(
            (value for value in all_df.get("enrichment_model", pd.Series(dtype=str)).astype(str) if value),
            "",
        )
        latest_prompt_version = next(
            (value for value in all_df.get("enrichment_prompt_version", pd.Series(dtype=str)).astype(str) if value),
            "",
        )
        st.markdown(
            f"""
            <div class="admin-box">
                <h4>Enrichment profile</h4>
                <p><strong>Model:</strong> {escape(latest_model or 'Not recorded yet')}</p>
                <p><strong>Prompt version:</strong> {escape(latest_prompt_version or 'Not recorded yet')}</p>
                <p><strong>Newest discovery:</strong> {escape(str(all_df['first_seen_at'].max()) if 'first_seen_at' in all_df.columns else 'Unknown')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if latest_run and latest_run.get("summary"):
        st.subheader("Latest run summary")
        st.markdown(latest_run["summary"])

    if health["last_run_errors"]:
        st.subheader("Latest run errors")
        st.code(health["last_run_errors"], language="text")
    elif latest_run:
        st.caption("No run errors recorded on the latest scrape.")
    else:
        _render_onboarding()
