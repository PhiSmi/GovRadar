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
    get_distinct_agencies,
    get_distinct_categories,
    get_overview_stats,
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
    for column in ["probable_tech_stack", "probable_roles", "themes"]:
        if column in clean.columns:
            clean[column] = clean[column].apply(
                lambda value: value if isinstance(value, list) else ([] if value in (None, "") else [str(value)])
            )

    if "relevance_score" in clean.columns:
        clean["relevance_score"] = pd.to_numeric(clean["relevance_score"], errors="coerce").fillna(0).astype(int)

    if "closing_date" in clean.columns:
        clean["closing_date"] = pd.to_datetime(clean["closing_date"], errors="coerce").dt.date

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
    if sort_mode == "Newest scrape":
        return df.sort_values(by=["date_scraped", "relevance_score"], ascending=[False, False], na_position="last")
    if sort_mode == "Agency":
        return df.sort_values(by=["agency", "relevance_score"], ascending=[True, False], na_position="last")
    return df.sort_values(by=["relevance_score", "closing_date"], ascending=[False, True], na_position="last")


def _chip_markup(items: list[str]) -> str:
    chips = "".join(f"<span class='chip'>{escape(str(item))}</span>" for item in items if str(item).strip())
    return f"<div class='chip-row'>{chips}</div>" if chips else ""


def _run_summary(runs: list[dict]) -> tuple[str, str]:
    if not runs:
        return "No scrape run recorded yet", "Connect a write-capable key and run the scraper once."

    latest = runs[0]
    raw_date = latest.get("run_date", "")
    try:
        stamp = pd.to_datetime(raw_date, utc=True)
        when = stamp.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        when = raw_date or "unknown"

    found = latest.get("tenders_found", 0)
    created = latest.get("tenders_new", 0)
    return f"Last scrape: {when}", f"{found} tenders processed, {created} new."


def _render_spotlight(row: pd.Series) -> None:
    status = str(row.get("status", "")).lower()
    badge_class = "badge-open" if status == "open" else "badge-closed"
    title = escape(str(row.get("title", "")))
    agency = escape(str(row.get("agency", "")))
    closing = row.get("closing_date") or "TBC"
    reason = escape(str(row.get("relevance_reasoning", "")))
    tech = row.get("probable_tech_stack", [])
    timeline = escape(str(row.get("estimated_seek_timeline", "")))
    url = row.get("gets_url", "")

    st.markdown(
        f"""
        <div class="spotlight">
            <div class="spotlight-top">
                <div class="spotlight-title">{title}</div>
                <span class="badge {badge_class}">{escape(status or 'unknown')}</span>
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


st.set_page_config(page_title="GovRadar", layout="wide")
_inject_styles()

runs: list[dict] = []
try:
    runs = load_scrape_history(limit=5)
except Exception:
    runs = []

headline, run_note = _run_summary(runs)

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
search_query = st.sidebar.text_input("Search tenders", placeholder="Agency, technology, role, keyword")
status_filter = st.sidebar.selectbox("Status", ["All", "open", "closed"])
min_relevance = st.sidebar.slider("Min relevance score", 0, 100, 40, 5)
high_priority_only = st.sidebar.toggle("Only show 70+ opportunities", value=False)
sort_mode = st.sidebar.selectbox(
    "Sort by",
    ["Highest relevance", "Closing soon", "Newest scrape", "Agency"],
)

distinct_agencies: list[str] = []
distinct_categories: list[str] = []
try:
    distinct_agencies, distinct_categories = load_filter_options()
except Exception:
    pass

agency_filter = st.sidebar.selectbox("Agency", ["All"] + distinct_agencies)
category_filter = st.sidebar.selectbox("Category", ["All"] + distinct_categories)

try:
    raw_tenders = load_tenders(
        status=status_filter if status_filter != "All" else None,
        min_relevance=min_relevance,
        agency=agency_filter if agency_filter != "All" else None,
        category=category_filter if category_filter != "All" else None,
    )
    df = _normalise_frame(pd.DataFrame(raw_tenders) if raw_tenders else pd.DataFrame())
except Exception as error:
    st.error(_format_data_error(error))
    df = pd.DataFrame()

filtered_df = _match_search(df, search_query)
if high_priority_only and not filtered_df.empty and "relevance_score" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["relevance_score"] >= 70]
filtered_df = _sort_frame(filtered_df, sort_mode)

try:
    stats = load_overview_stats()
except Exception:
    stats = {"total": 0, "open": 0, "high_relevance": 0}

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

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Tracked tenders", stats["total"])
col2.metric("Open tenders", stats["open"])
col3.metric("High relevance", stats["high_relevance"])
col4.metric("Closing in 21 days", len(closing_soon_df))
col5.metric("Average relevance", avg_relevance)

with st.sidebar:
    st.divider()
    st.subheader("Current view")
    st.caption(f"{len(filtered_df)} tenders after filters")
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

tab_overview, tab_pipeline, tab_agencies, tab_tech, tab_roles, tab_timeline, tab_themes = st.tabs(
    ["Overview", "Pipeline", "Agencies", "Tech", "Roles", "Timeline", "Themes"]
)

with tab_overview:
    if filtered_df.empty:
        st.info("No tenders match the current filters.")
    else:
        left, right = st.columns([1.35, 1.0], gap="large")

        with left:
            st.subheader("Opportunity spotlight")
            spotlight = filtered_df.head(6)
            for _, row in spotlight.iterrows():
                _render_spotlight(row)

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

with tab_pipeline:
    if filtered_df.empty:
        st.info("No tenders match the current filters.")
    else:
        st.subheader("Tender explorer")
        display_cols = [
            "title",
            "agency",
            "category",
            "tender_type",
            "closing_date",
            "relevance_score",
            "programme_size",
            "estimated_seek_timeline",
            "status",
            "gets_url",
        ]
        available = [column for column in display_cols if column in filtered_df.columns]
        st.dataframe(
            filtered_df[available],
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
                "gets_url": st.column_config.LinkColumn("GETS listing"),
            },
        )

        st.subheader("Tender details")
        for _, row in filtered_df.head(12).iterrows():
            title = row.get("title", "")
            agency = row.get("agency", "")
            relevance = row.get("relevance_score", 0)
            with st.expander(f"{title} | {agency} | relevance {relevance}"):
                a, b = st.columns(2)
                a.write(f"**Tender type:** {row.get('tender_type', '-') or '-'}")
                a.write(f"**Closing date:** {row.get('closing_date', '-') or '-'}")
                a.write(f"**Estimated value:** {row.get('estimated_value', '-') or '-'}")
                a.write(f"**Programme size:** {row.get('programme_size', '-') or '-'}")

                b.write(f"**Status:** {row.get('status', '-') or '-'}")
                b.write(f"**Category:** {row.get('category', '-') or '-'}")
                b.write(f"**Expected hiring window:** {row.get('estimated_seek_timeline', '-') or '-'}")
                b.write(f"**Relevance score:** {relevance}/100")

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

                url = row.get("gets_url", "")
                if url:
                    st.markdown(f"[Open in GETS]({url})")

with tab_agencies:
    try:
        agency_data = pd.DataFrame(load_agency_data())
        if agency_data.empty:
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
        if tech_data.empty:
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
        if role_data.empty:
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
    if filtered_df.empty or "estimated_seek_timeline" not in filtered_df.columns:
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
        if theme_data.empty:
            st.info("No theme data available yet.")
        else:
            st.subheader("Project themes")
            st.bar_chart(theme_data.head(20).set_index("theme")["mention_count"])
            st.dataframe(theme_data, hide_index=True, use_container_width=True)
    except Exception as error:
        st.error(f"Could not load theme data: {error}")
