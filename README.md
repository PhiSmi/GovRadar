# GovRadar

**NZ Government Tender Intelligence for IT/Digital/Health Professionals**

GovRadar monitors the NZ Government Electronic Tenders Service ([GETS](https://www.gets.govt.nz)) for IT, digital, health, and professional services tenders. Each tender is enriched with AI analysis (via Claude) to estimate relevance, likely tech stacks, roles needed, programme size, and when resulting job opportunities will appear on the market. Results are stored in Supabase and presented through a Streamlit dashboard.

The goal: **6-12 month advance visibility** on upcoming contract opportunities by watching what government agencies are tendering for today.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
  - [1. Database (Supabase)](#1-database-supabase)
  - [2. Environment Variables](#2-environment-variables)
  - [3. Install Dependencies](#3-install-dependencies)
- [Running the Scraper](#running-the-scraper)
  - [Manual Run](#manual-run)
  - [Automated (GitHub Actions)](#automated-github-actions)
  - [What the Scraper Does Step by Step](#what-the-scraper-does-step-by-step)
- [Running the Dashboard](#running-the-dashboard)
  - [Locally](#locally)
  - [Streamlit Community Cloud](#streamlit-community-cloud)
- [Dashboard Tabs](#dashboard-tabs)
- [Database Schema](#database-schema)
  - [Tables](#tables)
  - [Views](#views)
  - [Row Level Security](#row-level-security)
- [AI Enrichment](#ai-enrichment)
  - [What Gets Analysed](#what-gets-analysed)
  - [Relevance Profile](#relevance-profile)
  - [Changing the Profile](#changing-the-profile)
  - [Model and Cost](#model-and-cost)
- [Scraper Details](#scraper-details)
  - [Target Keywords](#target-keywords)
  - [Rate Limiting](#rate-limiting)
  - [GETS Page Structure](#gets-page-structure)
  - [Pagination](#pagination)
  - [Date Parsing](#date-parsing)
  - [Upsert Behaviour](#upsert-behaviour)
- [Configuration Reference](#configuration-reference)
- [Updating and Maintaining](#updating-and-maintaining)
  - [Adding New Keywords](#adding-new-keywords)
  - [Changing the AI Model](#changing-the-ai-model)
  - [Adjusting the Scrape Schedule](#adjusting-the-scrape-schedule)
  - [Changing Pagination Depth](#changing-pagination-depth)
  - [Modifying Dashboard Layout](#modifying-dashboard-layout)
  - [Adding New Database Columns](#adding-new-database-columns)
- [Architecture Decisions](#architecture-decisions)
- [Troubleshooting](#troubleshooting)
- [Future Iterations](#future-iterations)

---

## How It Works

```
GETS (gets.govt.nz)          Claude API              Supabase             Streamlit
┌─────────────────┐     ┌──────────────────┐    ┌──────────────┐    ┌──────────────┐
│  Listing pages  │────>│  Scraper parses  │───>│  AI enriches │───>│  Upsert to   │───>│  Dashboard   │
│  Detail pages   │     │  title, agency,  │    │  each tender │    │  tenders     │    │  reads and   │
│  (25 per page)  │     │  dates, desc     │    │  with Claude │    │  table       │    │  displays    │
└─────────────────┘     └──────────────────┘    └──────────────┘    └──────────────┘
        │                                                                    │
        │  2.5s delay between requests                                       │
        │  Respectful user-agent header                                      │
        └────────────────────────────────────────────────────────────────────┘
                              Daily via GitHub Actions (7:30am NZST)
```

1. **Scrape**: The scraper crawls GETS listing pages, fetches each tender's detail page, and filters for IT/digital/health relevance using keyword matching against the title and description.
2. **Enrich**: Each relevant tender is sent to Claude Sonnet for analysis. Claude returns structured JSON with tech stack predictions, role forecasts, relevance scoring, timeline estimates, and theme classification.
3. **Store**: Enriched tenders are upserted to Supabase (insert new, update existing) keyed on the GETS URL. Each run is tracked in a separate `tender_scrape_runs` table.
4. **Display**: The Streamlit dashboard reads from Supabase and presents the data across six analytical views with sidebar filters.

---

## Project Structure

```
govradar/
├── app.py                          # Streamlit dashboard (entry point for the UI)
├── scraper/
│   ├── __init__.py
│   ├── gets_scraper.py             # GETS web scraper — fetches and parses tenders
│   ├── enricher.py                 # Claude AI enrichment — analyses each tender
│   └── run.py                      # Orchestrator — ties scrape + enrich + store together
├── db/
│   ├── __init__.py
│   ├── client.py                   # Supabase client singleton
│   └── queries.py                  # All database read/write functions
├── setup/
│   └── schema.sql                  # Database schema — run once in Supabase SQL Editor
├── .github/
│   └── workflows/
│       └── scrape.yml              # GitHub Actions daily scrape workflow
├── requirements.txt                # Python dependencies
├── .env.example                    # Template for environment variables
├── .env                            # Your actual env vars (gitignored)
├── .gitignore
└── README.md                       # This file
```

---

## Prerequisites

- **Python 3.11+**
- **Supabase account** — free tier works fine. This project shares a Supabase project with ContractRadar (same project, different tables).
- **Anthropic API key** — for Claude AI enrichment. Each scrape run uses roughly 1 API call per relevant tender found.
- **GitHub account** — for the automated daily scrape via GitHub Actions (optional for local use).

---

## Setup

### 1. Database (Supabase)

1. Open your Supabase project dashboard.
2. Go to **SQL Editor**.
3. Paste the entire contents of `setup/schema.sql` and click **Run**.

This creates:
- `tender_scrape_runs` table (tracks each scrape execution)
- `tenders` table (the main data — raw fields + AI enrichment fields)
- 5 indexes for query performance
- 4 database views (`agency_activity`, `theme_summary`, `role_demand`, `tech_trends`)
- Row Level Security policies (public read, service-role write)

**Important**: You need two different Supabase keys for different purposes:
- **Publishable key** (`anon` key): Used by the Streamlit dashboard for read-only access. Find it in Supabase > Settings > API > `anon` `public`.
- **Service role key**: Used by the scraper for write access (inserts/updates). Find it in Supabase > Settings > API > `service_role`. **Never commit this key.**

### 2. Environment Variables

Copy the template:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-service-role-key-here
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

| Variable | Where to find it | Used by |
|---|---|---|
| `SUPABASE_URL` | Supabase > Settings > API > Project URL | Scraper + Dashboard |
| `SUPABASE_KEY` | Supabase > Settings > API > `service_role` (for scraper) or `anon` (for dashboard) | Scraper + Dashboard |
| `ANTHROPIC_API_KEY` | console.anthropic.com > API Keys | Scraper only |

The `.env` file is gitignored and will not be committed.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Dependencies:
| Package | Version | Purpose |
|---|---|---|
| `streamlit` | >= 1.30.0 | Dashboard web framework |
| `supabase` | >= 2.0.0 | Database client |
| `anthropic` | >= 0.40.0 | Claude API client for AI enrichment |
| `requests` | >= 2.31.0 | HTTP requests for scraping GETS |
| `beautifulsoup4` | >= 4.12.0 | HTML parsing |
| `pandas` | >= 2.0.0 | Data manipulation in the dashboard |

---

## Running the Scraper

### Manual Run

From the project root:

```bash
python -m scraper.run
```

This will:
1. Create a new scrape run record in `tender_scrape_runs`.
2. Crawl up to 11 pages of GETS listings (275 tenders max).
3. Fetch the detail page for each tender (with 2.5s delay between requests).
4. Filter for IT/digital/health relevance using keyword matching.
5. Send each relevant tender to Claude for AI analysis.
6. Upsert results to the `tenders` table in Supabase.
7. Update the scrape run record with counts and any errors.

Logs are printed to stdout with timestamps:

```
08:30:01 INFO Starting GETS scrape...
08:30:04 INFO Fetching listing page 1...
08:30:04 INFO   Found 25 tenders on page 1
08:30:07 INFO   Fetching detail: Ministry of Health IT Modernisation...
08:30:09 INFO   ✓ Relevant: Ministry of Health IT Modernisation
...
08:35:22 INFO Done — 18 found, 12 new, 0 errors
```

**Expected runtime**: 10-30 minutes depending on how many tenders are on GETS and how many are relevant (2.5s per GETS page request + 1s per Claude API call).

### Automated (GitHub Actions)

The workflow at `.github/workflows/scrape.yml` runs the scraper automatically.

**Schedule**: Daily at `18:30 UTC` which is approximately **7:30am NZST** (or 7:30am NZDT during daylight saving — GitHub Actions uses UTC so the local time shifts by one hour with DST).

**Manual trigger**: You can also run it on-demand from the GitHub Actions tab > "Daily GETS Scrape" > "Run workflow".

**Required GitHub secrets** (Settings > Secrets and variables > Actions):

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase **service role** key |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

### What the Scraper Does Step by Step

```
scraper/run.py          →  Orchestrator
  ├── creates scrape run record in DB
  ├── calls scrape_gets()
  │     ├── fetches GETS index page (page 1)
  │     ├── parses listing table rows
  │     ├── paginates through pages 2-11
  │     ├── for each tender listing:
  │     │     ├── fetches the detail page
  │     │     ├── parses description, category, agency, dates, value
  │     │     └── checks relevance via keyword matching
  │     └── returns list of RawTender objects
  ├── calls enrich_all()
  │     └── for each tender:
  │           ├── sends title + agency + type + description to Claude
  │           ├── Claude returns JSON with analysis
  │           └── merges raw data + enrichment into a dict
  └── for each enriched tender:
        ├── checks if it already exists (by gets_url)
        ├── upserts to tenders table
        └── updates scrape run with final counts
```

---

## Running the Dashboard

### Locally

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Requires `SUPABASE_URL` and `SUPABASE_KEY` to be set (either in `.env` or as environment variables).

**Tip**: For local dashboard use, the publishable/anon key is sufficient since the dashboard only reads data.

### Streamlit Community Cloud

1. Push the repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and deploy from your repo.
3. Set the main file path to `app.py`.
4. In the Streamlit Cloud app settings, add secrets:

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
```

The dashboard reads secrets via `st.secrets` and falls back to environment variables. You do not need the Anthropic API key for the dashboard — it only reads from the database.

---

## Dashboard Tabs

### Pipeline
The main view. Shows a sortable table of all tenders matching your filters with columns: title, agency, tender type, closing date, relevance score, programme size, estimated Seek timeline, and status.

Below the table are **expandable detail cards** for the top 20 tenders. Each card shows:
- Tender type, closing date, estimated value, programme size
- Relevance score (0-100), Seek timeline, category
- Why it's relevant (AI reasoning)
- Probable tech stack, roles needed, themes
- Link to the original GETS page

### Agency Activity
Bar chart and table showing which agencies are tendering most frequently. Columns: agency name, total tender count, open tender count, average relevance score.

### Tech Trends
Bar chart and table of technologies appearing across tenders (e.g. AWS, Salesforce, REST APIs). Shows which technologies government agencies are buying — useful for upskilling decisions.

### Role Demand
Bar chart and table of roles tenders will likely generate (e.g. Business Analyst, Solution Architect, Developer). Shows what the market will need.

### Timeline
Groups tenders by their estimated Seek timeline (3/6/9/12 months). Shows when current tenders will likely result in contractor/job postings.

### Themes
Bar chart and table of themes across tenders (e.g. modernisation, migration, greenfield, regulatory, integration). Shows the nature of upcoming work.

### Sidebar
- **Filters**: Status (All/open/closed), minimum relevance score (slider 0-100), agency dropdown, category dropdown.
- **Scrape history**: Shows the last 5 scrape runs with date, tenders found, and new tenders added.

---

## Database Schema

### Tables

#### `tender_scrape_runs`
Tracks each execution of the scraper.

| Column | Type | Description |
|---|---|---|
| `id` | uuid (PK) | Auto-generated |
| `run_date` | timestamptz | When the scrape ran |
| `tenders_found` | int | Total relevant tenders found in this run |
| `tenders_new` | int | How many were new (not previously seen) |
| `errors` | text | Error messages, if any (semicolon-separated) |

#### `tenders`
The main table — one row per tender. Combines raw scraped data with AI enrichment.

| Column | Type | Description |
|---|---|---|
| `id` | uuid (PK) | Auto-generated |
| `title` | text | Tender title from GETS |
| `agency` | text | Government agency / buyer |
| `closing_date` | date | When the tender closes for submissions |
| `category` | text | UNSPSC procurement category |
| `description` | text | Full description from the GETS detail page |
| `gets_url` | text (unique) | URL to the tender on GETS — used as dedup key |
| `tender_type` | text | RFP, RFI, ROI, EOI, RFQ, RFT, NOI, etc. |
| `estimated_value` | text | Contract value if shown on GETS |
| `status` | text | `open` or `closed` — derived from closing date |
| `date_scraped` | timestamptz | When we first scraped this tender |
| `probable_tech_stack` | text[] | AI-predicted technologies (PostgreSQL array) |
| `probable_roles` | text[] | AI-predicted roles needed |
| `programme_size` | text | `small`, `medium`, `large`, or `mega` |
| `relevance_score` | int | 0-100 relevance to your profile |
| `relevance_reasoning` | text | One-sentence explanation of the score |
| `estimated_seek_timeline` | text | `3 months`, `6 months`, `9 months`, or `12 months` |
| `themes` | text[] | AI-identified themes (modernisation, migration, etc.) |
| `scrape_run_id` | uuid (FK) | Links to `tender_scrape_runs.id` |

### Views

These are database views that auto-aggregate data from the `tenders` table. The dashboard queries them directly.

| View | What it shows |
|---|---|
| `agency_activity` | Agency name, total tender count, open count, average relevance. Ordered by tender count descending. |
| `theme_summary` | Each theme and how many tenders mention it. Uses PostgreSQL `unnest()` on the themes array. |
| `role_demand` | Each role, demand count, and average relevance of tenders needing that role. |
| `tech_trends` | Each technology and how many tenders mention it. |

### Row Level Security

Both tables have RLS enabled:
- **Read**: Public (anyone with the anon key can read — the dashboard uses this).
- **Insert/Update**: Open policies (the service role key is needed for actual writes through the Supabase client).

### Indexes

| Index | Column(s) | Purpose |
|---|---|---|
| `idx_tenders_relevance` | `relevance_score DESC` | Fast sorting by relevance |
| `idx_tenders_closing` | `closing_date` | Date range queries |
| `idx_tenders_agency` | `agency` | Agency filter |
| `idx_tenders_status` | `status` | Open/closed filter |
| `idx_tenders_date_scraped` | `date_scraped DESC` | Recent tenders first |

---

## AI Enrichment

### What Gets Analysed

For each tender, Claude receives:
- Title
- Agency
- Tender type (RFP/RFI/etc.)
- Category
- Estimated value
- Description (first 4,000 characters)

### What Claude Returns

A structured JSON object with:

| Field | Type | Example |
|---|---|---|
| `probable_tech_stack` | string array | `["AWS", "Salesforce", "REST APIs", "Azure AD"]` |
| `probable_roles` | string array | `["Business Analyst", "Solution Architect", "Developer"]` |
| `programme_size` | string | `"large"` |
| `relevance_score` | int (0-100) | `82` |
| `relevance_reasoning` | string | `"Large-scale health system integration aligning with BA/integration experience"` |
| `estimated_seek_timeline` | string | `"6 months"` |
| `themes` | string array | `["modernisation", "integration", "health"]` |

### Relevance Profile

The AI scoring is calibrated to this profile (defined in `scraper/enricher.py`):

> Senior Technical Business Analyst / Integration Analyst with 10+ years experience across NZ government, health, and banking sectors. Key skills: API design, integration architecture, AWS, Azure, Salesforce, data migration, requirements analysis, stakeholder management.

A score of **70+** is considered "high relevance" and is tracked as a metric on the dashboard.

### Changing the Profile

Edit the `ENRICHMENT_PROMPT` string in `scraper/enricher.py` (line 15). Update the user description paragraph to match a different role/skillset. The AI will recalibrate all future scores accordingly. Existing tenders in the database will keep their old scores unless you re-run enrichment.

### Model and Cost

- **Model**: `claude-sonnet-4-20250514` (Claude Sonnet 4)
- **Max tokens per call**: 1,024
- **Approximate cost**: ~$0.01-0.03 per tender (depends on description length)
- **Typical run**: 10-50 relevant tenders = ~$0.10-$1.50 per daily run

---

## Scraper Details

### Target Keywords

The scraper filters tenders by checking if any of these keywords appear in the title or description (case-insensitive). Defined in `scraper/gets_scraper.py`:

```
information technology, digital, software, data, cloud, cyber,
integration, system, platform, health, ICT, API, infrastructure,
analytics, migration, modernisation, modernization, transformation,
professional services, consulting, advisory
```

A tender only needs to match **one** keyword to be considered relevant and sent for AI enrichment.

### Rate Limiting

- **2.5 seconds** between every HTTP request to GETS (`DELAY` constant in `gets_scraper.py`).
- **1.0 seconds** between Claude API calls (`delay` parameter in `enrich_all()`).
- Custom `User-Agent` header: `GovRadar/1.0 (NZ tender monitor)`.
- Uses `requests.Session()` for connection reuse.

### GETS Page Structure

- **Index page**: `https://www.gets.govt.nz/ExternalIndex.htm` — shows 25 tenders per page in a table.
- **Pagination**: `?page=2`, `?page=3`, etc.
- **Detail pages**: `https://www.gets.govt.nz/{ORG_CODE}/ExternalTenderDetails.htm?id={NUMERIC_ID}` — contains the full description, metadata, category, and value.
- **Table columns**: RFx ID, Reference, Title, Tender Type, Close Date, Organisation.

The scraper does not use JavaScript rendering — GETS serves HTML directly. No need for Playwright or Selenium.

### Pagination

Default: crawls up to **11 pages** (275 tenders). Stops early if a page returns no results. Change via `max_pages` parameter:

```python
# In scraper/run.py, modify the run() call:
tenders = scrape_gets(max_pages=5)   # fewer pages, faster run
tenders = scrape_gets(max_pages=20)  # deeper crawl
```

### Date Parsing

GETS uses various date formats. The scraper handles:
- `15 Mar 2026 2:00 PM (NZDT)` — strips timezone parenthetical
- `15 Mar 2026 14:00`
- `15 Mar 2026`
- `15/03/2026 2:00 PM`
- `15/03/2026`

All dates are stored as ISO format (`YYYY-MM-DD`) in the database.

### Upsert Behaviour

Tenders are upserted on the `gets_url` column (which has a unique constraint). This means:
- **New tenders**: Inserted with all fields.
- **Existing tenders**: Updated with the latest scraped data (description, status, enrichment, etc.).
- This is safe to run multiple times — it will not create duplicates.

---

## Configuration Reference

| What | Where | Default |
|---|---|---|
| Scrape delay between requests | `scraper/gets_scraper.py` line 24 (`DELAY`) | `2.5` seconds |
| Maximum pages to crawl | `scraper/run.py` line 25 / `gets_scraper.py` `max_pages` param | `11` (275 tenders) |
| Relevance keywords | `scraper/gets_scraper.py` lines 27-49 (`TARGET_KEYWORDS`) | 20 keywords |
| AI model | `scraper/enricher.py` line 60 | `claude-sonnet-4-20250514` |
| AI max tokens | `scraper/enricher.py` line 61 | `1024` |
| AI delay between calls | `scraper/enricher.py` line 104 (`delay` param) | `1.0` seconds |
| Description truncation (AI input) | `scraper/enricher.py` line 55 | `4000` chars |
| Description truncation (DB storage) | `scraper/enricher.py` line 123 | `10000` chars |
| Relevance profile | `scraper/enricher.py` lines 15-19 (`ENRICHMENT_PROMPT`) | Senior Tech BA / Integration |
| Dashboard tender limit | `db/queries.py` line 14 (`limit` param) | `200` |
| Dashboard detail cards shown | `app.py` line 99 (`df.head(20)`) | `20` |
| High relevance threshold | `db/queries.py` line 90 | `70` |
| GitHub Actions schedule | `.github/workflows/scrape.yml` line 7 | `30 18 * * *` (UTC) |

---

## Updating and Maintaining

### Adding New Keywords

Edit the `TARGET_KEYWORDS` list in `scraper/gets_scraper.py`. Add or remove keywords as needed:

```python
TARGET_KEYWORDS = [
    "information technology",
    "digital",
    # ... existing keywords ...
    "machine learning",     # add new ones
    "AI",
]
```

Changes take effect on the next scrape run. Existing tenders in the database are not re-evaluated — only new scrapes use the updated keywords.

### Changing the AI Model

Edit `scraper/enricher.py` line 60:

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",  # change this
    max_tokens=1024,
    ...
)
```

### Adjusting the Scrape Schedule

Edit `.github/workflows/scrape.yml`:

```yaml
on:
  schedule:
    - cron: "30 18 * * *"    # change this — uses UTC, 5-field cron
```

Examples:
- `"0 20 * * *"` — 8:00am NZST daily
- `"30 18 * * 1-5"` — 7:30am NZST weekdays only
- `"0 6,18 * * *"` — twice daily at 6pm and 6am UTC

### Changing Pagination Depth

Edit `scraper/run.py` line 25:

```python
tenders = scrape_gets(max_pages=11)  # change the number
```

Each page has ~25 tenders. More pages = longer runtime but catches older tenders.

### Modifying Dashboard Layout

Edit `app.py`. The dashboard uses standard Streamlit components:
- `st.tabs()` for the main navigation
- `st.dataframe()` for tables
- `st.bar_chart()` for charts
- `st.expander()` for tender detail cards
- `st.sidebar` for filters

### Adding New Database Columns

1. Add the column in Supabase SQL Editor:
   ```sql
   alter table tenders add column new_field text;
   ```
2. Update `setup/schema.sql` to include the new column (for future fresh installs).
3. Update `scraper/enricher.py` to include the new field in the enrichment prompt and parse it from Claude's response.
4. Update `db/queries.py` if you need specific query support.
5. Update `app.py` to display the new field in the dashboard.

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| **Requests + BeautifulSoup** (not Playwright) | GETS serves static HTML — no JS rendering needed. Simpler, faster, fewer dependencies. |
| **Supabase** (not SQLite) | Shared with ContractRadar. Accessible from both GitHub Actions and Streamlit Cloud without file system. |
| **Upsert on gets_url** | GETS URLs are unique per tender. Safe for repeated runs without duplicates. |
| **Database views** for aggregations | Aggregation logic lives in PostgreSQL, not Python. Views auto-update as data changes. |
| **Keyword pre-filter before AI** | Avoids sending every tender to Claude. Only relevant ones get enriched, saving API costs. |
| **Description capped at 4,000 chars for AI** | Keeps Claude costs down. Most tender overviews are well under 4,000 chars. |
| **Singleton Supabase client** | Same pattern as ContractRadar. One connection reused across all queries. |
| **Streamlit** (not Next.js/React) | Fast to build, easy to deploy, good for data-heavy dashboards. Free hosting on Streamlit Cloud. |

---

## Troubleshooting

### "SUPABASE_URL and SUPABASE_KEY must be set"
Your environment variables are not loaded. Make sure `.env` exists and contains valid values. If running via GitHub Actions, check that the secrets are set in the repo settings.

### Scraper finds 0 tenders
- GETS may have changed their HTML structure. Check the listing table class name (`contentTable`) in `gets_scraper.py`.
- The keyword list may be too narrow. Try adding broader terms.
- GETS may be temporarily down.

### "Failed to parse Claude response"
Claude occasionally returns malformed JSON. The enricher handles this gracefully by returning empty enrichment with `relevance_score: 0`. Check the logs for the specific tender.

### Dashboard shows no data
- Run the scraper at least once to populate the database.
- Check that the dashboard's `SUPABASE_KEY` has read access (the anon/publishable key works for reads).
- Check the Supabase dashboard > Table Editor to verify data exists in the `tenders` table.

### GitHub Actions workflow not running
- Check that the workflow file is on the `main` branch.
- Verify secrets are set: Settings > Secrets and variables > Actions.
- GitHub Actions cron schedules can have up to 15 minutes of delay.
- You can always trigger manually from the Actions tab.

### RLS blocking writes
If you get permission errors when the scraper tries to insert/update, you're likely using the anon key instead of the service role key. The scraper needs the **service role key** for write operations.

---

## Future Iterations

- **PDF attachment parsing** — many tenders reference PDF documents with full RFP details. Parsing these would improve AI analysis accuracy.
- **Email/Slack alerts** — notify when a high-relevance tender appears.
- **Historical trend analysis** — track how agency spending patterns change over time.
- **Advanced GETS search** — use the advanced search form to filter by specific UNSPSC categories instead of keyword matching.
- **Re-enrichment** — re-run AI analysis on existing tenders when the relevance profile changes.
- **Tender status tracking** — monitor open tenders for status changes (awarded, cancelled).
