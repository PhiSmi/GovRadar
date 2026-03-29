"""GovRadar — NZ Government Tender Intelligence Dashboard."""

import os
import streamlit as st
import pandas as pd

# Supabase env vars for Streamlit Cloud
os.environ.setdefault("SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
os.environ.setdefault("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY", ""))

from db.queries import (
    get_tenders,
    get_agencies,
    get_role_demand,
    get_tech_trends,
    get_theme_summary,
    get_overview_stats,
    get_scrape_runs,
    get_distinct_agencies,
    get_distinct_categories,
)

st.set_page_config(page_title="GovRadar", page_icon="📡", layout="wide")

st.title("📡 GovRadar")
st.caption("NZ Government Tender Intelligence — IT / Digital / Health")

# ── Sidebar filters ───────────────────────────────────────────────────

st.sidebar.header("Filters")

status_filter = st.sidebar.selectbox("Status", ["All", "open", "closed"])
min_relevance = st.sidebar.slider("Min relevance score", 0, 100, 0, 5)

try:
    agencies = ["All"] + get_distinct_agencies()
except Exception:
    agencies = ["All"]
agency_filter = st.sidebar.selectbox("Agency", agencies)

try:
    categories = ["All"] + get_distinct_categories()
except Exception:
    categories = ["All"]
category_filter = st.sidebar.selectbox("Category", categories)

# ── Fetch data ────────────────────────────────────────────────────────

try:
    tenders = get_tenders(
        status=status_filter if status_filter != "All" else None,
        min_relevance=min_relevance,
        agency=agency_filter if agency_filter != "All" else None,
        category=category_filter if category_filter != "All" else None,
    )
    df = pd.DataFrame(tenders) if tenders else pd.DataFrame()
except Exception as e:
    st.error(f"Could not load tenders: {e}")
    df = pd.DataFrame()

# ── Overview stats ────────────────────────────────────────────────────

try:
    stats = get_overview_stats()
except Exception:
    stats = {"total": 0, "open": 0, "high_relevance": 0}

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total tenders", stats["total"])
col2.metric("Open", stats["open"])
col3.metric("High relevance (70+)", stats["high_relevance"])
col4.metric("Showing", len(df))

# ── Tabs ──────────────────────────────────────────────────────────────

tab_pipeline, tab_agencies, tab_tech, tab_roles, tab_timeline, tab_themes = st.tabs(
    ["Pipeline", "Agency Activity", "Tech Trends", "Role Demand", "Timeline", "Themes"]
)

# ── Pipeline tab ──────────────────────────────────────────────────────

with tab_pipeline:
    if df.empty:
        st.info("No tenders match your filters.")
    else:
        display_cols = [
            "title", "agency", "tender_type", "closing_date", "relevance_score",
            "programme_size", "estimated_seek_timeline", "status",
        ]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].sort_values("relevance_score", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        # Expandable detail cards
        st.subheader("Tender details")
        for _, row in df.head(20).iterrows():
            with st.expander(f"{'🟢' if row.get('status') == 'open' else '🔴'} {row.get('title', '')} — {row.get('agency', '')}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Type:** {row.get('tender_type', '—')}")
                c1.write(f"**Closing:** {row.get('closing_date', '—')}")
                c1.write(f"**Value:** {row.get('estimated_value', '—')}")
                c1.write(f"**Size:** {row.get('programme_size', '—')}")

                c2.write(f"**Relevance:** {row.get('relevance_score', 0)}/100")
                c2.write(f"**Seek timeline:** {row.get('estimated_seek_timeline', '—')}")
                c2.write(f"**Category:** {row.get('category', '—')}")

                st.write(f"**Why relevant:** {row.get('relevance_reasoning', '—')}")

                tech = row.get("probable_tech_stack", [])
                if tech:
                    st.write(f"**Tech stack:** {', '.join(tech) if isinstance(tech, list) else tech}")

                roles = row.get("probable_roles", [])
                if roles:
                    st.write(f"**Roles needed:** {', '.join(roles) if isinstance(roles, list) else roles}")

                themes = row.get("themes", [])
                if themes:
                    st.write(f"**Themes:** {', '.join(themes) if isinstance(themes, list) else themes}")

                url = row.get("gets_url", "")
                if url:
                    st.markdown(f"[View on GETS]({url})")

# ── Agency Activity tab ──────────────────────────────────────────────

with tab_agencies:
    try:
        agency_data = get_agencies()
        if agency_data:
            adf = pd.DataFrame(agency_data)
            st.bar_chart(adf.set_index("agency")["tender_count"].head(20))
            st.dataframe(adf, use_container_width=True, hide_index=True)
        else:
            st.info("No agency data yet.")
    except Exception as e:
        st.error(f"Could not load agency data: {e}")

# ── Tech Trends tab ──────────────────────────────────────────────────

with tab_tech:
    try:
        tech_data = get_tech_trends()
        if tech_data:
            tdf = pd.DataFrame(tech_data)
            st.bar_chart(tdf.set_index("technology")["mention_count"].head(25))
            st.dataframe(tdf, use_container_width=True, hide_index=True)
        else:
            st.info("No tech trend data yet.")
    except Exception as e:
        st.error(f"Could not load tech trends: {e}")

# ── Role Demand tab ──────────────────────────────────────────────────

with tab_roles:
    try:
        role_data = get_role_demand()
        if role_data:
            rdf = pd.DataFrame(role_data)
            st.bar_chart(rdf.set_index("role")["demand_count"].head(20))
            st.dataframe(rdf, use_container_width=True, hide_index=True)
        else:
            st.info("No role demand data yet.")
    except Exception as e:
        st.error(f"Could not load role demand: {e}")

# ── Timeline tab ─────────────────────────────────────────────────────

with tab_timeline:
    if df.empty or "estimated_seek_timeline" not in df.columns:
        st.info("No timeline data available.")
    else:
        timeline_counts = df["estimated_seek_timeline"].value_counts()
        st.bar_chart(timeline_counts)

        st.subheader("Opportunities by expected Seek timeline")
        for period in ["3 months", "6 months", "9 months", "12 months"]:
            subset = df[df["estimated_seek_timeline"] == period]
            if not subset.empty:
                st.write(f"**{period}** — {len(subset)} tenders")
                for _, row in subset.iterrows():
                    st.write(f"- {row.get('title', '')} ({row.get('agency', '')})")

# ── Themes tab ────────────────────────────────────────────────────────

with tab_themes:
    try:
        theme_data = get_theme_summary()
        if theme_data:
            thdf = pd.DataFrame(theme_data)
            st.bar_chart(thdf.set_index("theme")["mention_count"].head(20))
            st.dataframe(thdf, use_container_width=True, hide_index=True)
        else:
            st.info("No theme data yet.")
    except Exception as e:
        st.error(f"Could not load theme data: {e}")

# ── Footer: scrape run history ────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.subheader("Scrape history")
    try:
        runs = get_scrape_runs(limit=5)
        if runs:
            for r in runs:
                date = r.get("run_date", "")[:10]
                st.caption(f"{date}: {r.get('tenders_found', 0)} found, {r.get('tenders_new', 0)} new")
        else:
            st.caption("No scrape runs yet.")
    except Exception:
        st.caption("Could not load scrape history.")
