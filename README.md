# GovRadar

## What is this?

If you work in IT contracting or consulting in New Zealand, you've probably noticed a pattern: by the time a role appears on Seek or a recruiter calls you, the project has already been in motion for months. The agency tendered on GETS six months ago, a vendor won the work three months ago, and now they're finally hiring. You're always reacting.

GovRadar flips that around. It watches the [NZ Government Electronic Tenders Service (GETS)](https://www.gets.govt.nz) every day, pulls down tenders related to IT, digital, health, and professional services, and runs each one through an AI model to answer the questions that actually matter to a contractor:

- What tech stack will this probably involve?
- What roles will they need?
- How big is this programme?
- How relevant is this to *my* specific skills and experience?
- When will this likely turn into actual job postings on Seek?

The result is a live dashboard that gives you **6-12 months of advance visibility** on where the market is heading — which agencies are spending, what technologies they're buying, and when the opportunities will materialise.

---

## Who is this for?

GovRadar was built for a specific persona — a Senior Technical BA / Integration Analyst with deep NZ government and health sector experience — but the relevance profile is fully configurable. If you're any kind of IT professional working in or around NZ government, you can adapt it to your own skills and watch the tenders that matter to you.

Typical users:
- **IT contractors** who want early signal on upcoming programmes before recruiters get involved
- **Consultants** scoping which agencies are active and what kind of work is coming up
- **Team leads or practice managers** at consultancies tracking where to position their people
- **Anyone curious** about what the NZ government is actually spending on in the tech space

---

## What does it actually look like?

The dashboard has six views, all fed from the same data:

**Pipeline** — the main table. Every tender sorted by how relevant it is to you, with expandable cards showing the AI's full analysis. You see the title, the agency, closing date, relevance score, programme size, and when roles will likely hit the market. Click into any tender for tech stack predictions, role forecasts, themes, and a direct link to the GETS listing.

**Agency Activity** — which government agencies are tendering the most. If the Ministry of Health has put out 12 tenders this quarter and most of them score 80+ for you, that's a signal worth paying attention to.

**Tech Trends** — aggregate view of what technologies are appearing across tenders. If AWS keeps showing up more than Azure, or if Salesforce mentions are climbing, that tells you where to invest your upskilling time.

**Role Demand** — what roles tenders are likely to generate. Business Analysts, Solution Architects, Developers, Testers — see what the market will need before the market knows it needs it.

**Timeline** — groups everything by when opportunities will likely appear. "3 months" means roles from this tender could hit Seek soon. "12 months" means it's early days but worth tracking.

**Themes** — the nature of the work. Modernisation, migration, greenfield, regulatory compliance, integration. Shows you what kind of projects are dominating.

The sidebar has filters for status (open/closed), minimum relevance score, specific agency, and category. At the bottom it shows your recent scrape history so you know the data is fresh.

---

## How it works

There are three moving parts: a scraper, an AI enrichment step, and a dashboard. They're connected by a Supabase database.

### The scraper

Every morning at 7:30am NZST (via GitHub Actions, or whenever you run it manually), the scraper hits GETS and works through the tender listings. GETS shows 25 tenders per page in an HTML table. The scraper:

1. Loads the listing pages (up to 11 pages, so ~275 tenders)
2. For each tender, follows the link to its detail page to get the full description
3. Checks whether the tender is relevant using keyword matching — does the title or description mention things like "digital", "integration", "cloud", "health", "API", "migration", etc.
4. If it's relevant, keeps it. If not, skips it.

The scraper is polite — it waits 2.5 seconds between every request and identifies itself with a custom user agent. GETS serves plain HTML so there's no need for browser automation.

### The AI enrichment

Each relevant tender gets sent to Claude (Anthropic's AI) for structured analysis. The prompt includes the tender title, agency, type, category, estimated value, and description. Claude returns a JSON object with:

- **Probable tech stack** — what technologies this project will likely involve
- **Probable roles** — what positions the programme will need to fill
- **Programme size** — small, medium, large, or mega
- **Relevance score** — 0 to 100, calibrated against your professional profile
- **Relevance reasoning** — a one-sentence explanation of why it scored the way it did
- **Estimated Seek timeline** — when this tender will likely result in job postings (3, 6, 9, or 12 months)
- **Themes** — modernisation, migration, greenfield, regulatory, integration, etc.

The model used is Claude Sonnet 4. Each tender costs roughly 1-3 cents to analyse, so a typical daily run with 10-50 relevant tenders costs between 10 cents and $1.50.

### The database

Everything lands in Supabase (PostgreSQL). Two tables: `tenders` for the data and `tender_scrape_runs` for tracking each execution. Four database views handle the aggregations (agency activity, tech trends, role demand, theme summary) so the dashboard just reads pre-computed data.

Tenders are upserted on their GETS URL, so running the scraper twice on the same day is harmless — it'll update existing records rather than creating duplicates.

### The dashboard

A Streamlit app that reads from Supabase and renders the six views described above. Runs locally or deploys to Streamlit Community Cloud for free. The dashboard only needs read access to the database — it never writes anything.

---

## A day in the life

Here's what using GovRadar actually looks like in practice:

**Monday morning, 7:35am** — GitHub Actions has already run the scraper. You open the dashboard over coffee and check the Pipeline tab. Three new tenders appeared over the weekend. One is a large health sector integration programme from Te Whatu Ora — relevance score 87. The AI thinks it'll need BAs, Solution Architects, and Integration Developers, probably using Azure and HL7/FHIR. Estimated timeline: 6 months before roles appear on Seek.

**You note it down.** In six months you'll be wrapping up your current contract. This could be the next one.

**Thursday** — you check the Agency Activity tab and notice the Ministry of Business, Innovation and Employment has gone from 2 tenders last month to 7 this month. Something is happening over there. You switch to Tech Trends and see Salesforce mentions have doubled in the last few weeks. Maybe worth brushing up on that Salesforce cert.

**End of month** — you look at the Timeline view. There are 4 tenders in the "3 months" bucket, all scoring above 70. That aligns with when your current contract ends. You start reaching out to recruiters who work with those agencies, armed with specific knowledge about what's coming.

**None of this information is secret.** It's all on GETS, publicly available. GovRadar just saves you from manually trawling through hundreds of tenders, most of which are for road construction or office supplies, and adds the analytical layer that turns raw tender data into career intelligence.

---

## Tech stack

| Component | Technology | Why |
|---|---|---|
| **Scraper** | Python, Requests, BeautifulSoup | GETS serves static HTML — no JS rendering needed, so lightweight HTTP requests and HTML parsing are enough |
| **AI enrichment** | Anthropic Claude API (Sonnet 4) | Structured analysis of unstructured tender descriptions — tech stack prediction, role forecasting, relevance scoring |
| **Database** | Supabase (PostgreSQL) | Hosted PostgreSQL with a Python SDK, accessible from GitHub Actions and Streamlit Cloud without managing infrastructure. Shares a project with ContractRadar |
| **Dashboard** | Streamlit | Rapid data-focused web apps. Free hosting on Streamlit Community Cloud. Good for tables, charts, and filters without writing frontend code |
| **Automation** | GitHub Actions | Free CI/CD for public repos. Runs the scraper on a daily cron schedule |
| **Language** | Python 3.11+ | Everything is Python — scraper, enrichment, database layer, dashboard |

Dependencies (all in `requirements.txt`):
- `streamlit` — dashboard framework
- `supabase` — database client
- `anthropic` — Claude API client
- `requests` — HTTP for scraping
- `beautifulsoup4` — HTML parsing
- `pandas` — data manipulation in the dashboard

---

## Project structure

```
govradar/
├── app.py                          # Streamlit dashboard — the main UI
├── scraper/
│   ├── gets_scraper.py             # Scrapes GETS listing + detail pages
│   ├── enricher.py                 # Sends tenders to Claude for AI analysis
│   └── run.py                      # Orchestrator — scrape, enrich, store
├── db/
│   ├── client.py                   # Supabase connection (singleton pattern)
│   └── queries.py                  # All database reads and writes
├── setup/
│   └── schema.sql                  # Tables, views, indexes, RLS — run once in Supabase
├── .github/
│   └── workflows/
│       └── scrape.yml              # Daily GitHub Actions cron job
├── requirements.txt
├── .env.example                    # Template for your secrets
├── .env                            # Your actual secrets (gitignored)
└── .gitignore
```

---

## Getting started

### 1. Set up the database

Open your Supabase project, go to the **SQL Editor**, paste the contents of `setup/schema.sql`, and run it. This creates everything — tables, views, indexes, and security policies.

You'll need two keys from Supabase (Settings > API):
- The **anon/publishable key** — for the dashboard (read-only)
- The **service role key** — for the scraper (read + write). Keep this one secret.

### 2. Configure environment variables

```bash
cp .env.example .env
```

Fill in your `.env`:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-service-role-key
ANTHROPIC_API_KEY=sk-ant-api03-your-key
```

### 3. Install and run

```bash
pip install -r requirements.txt

# Run the scraper (first run populates the database)
python -m scraper.run

# Launch the dashboard
streamlit run app.py
```

The scraper takes 10-30 minutes depending on how many tenders are on GETS. It logs progress as it goes:

```
08:30:01 INFO Starting GETS scrape...
08:30:04 INFO Fetching listing page 1...
08:30:04 INFO   Found 25 tenders on page 1
08:30:07 INFO   Fetching detail: Ministry of Health IT Modernisation...
08:30:09 INFO   ✓ Relevant: Ministry of Health IT Modernisation
...
08:35:22 INFO Done — 18 found, 12 new, 0 errors
```

The dashboard opens at `http://localhost:8501`.

### 4. Automate it

Push the repo to GitHub and add three secrets to your repository (Settings > Secrets and variables > Actions):

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase service role key |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

The GitHub Actions workflow runs the scraper every day at 7:30am NZST. You can also trigger it manually from the Actions tab.

### 5. Deploy the dashboard

For always-on access, deploy to Streamlit Community Cloud:

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Set `app.py` as the main file
4. Add secrets in the Streamlit Cloud settings:

```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_KEY = "your-anon-key"
```

Note: the dashboard only needs the anon key, not the service role key.

---

## How the scraper decides what's relevant

Before any tender gets sent to Claude (which costs money), the scraper does a quick keyword check. If the title or description contains any of these terms, it's considered relevant:

> information technology, digital, software, data, cloud, cyber, integration, system, platform, health, ICT, API, infrastructure, analytics, migration, modernisation, modernization, transformation, professional services, consulting, advisory

A tender only needs to match one keyword. This casts a deliberately wide net — the AI enrichment step then assigns a proper relevance score that separates the genuinely interesting tenders from the noise.

You can edit this list in `scraper/gets_scraper.py` (the `TARGET_KEYWORDS` list). Add `"machine learning"` or `"security"` or whatever matches your interests. Changes apply on the next scrape run.

---

## How the AI scoring works

The enrichment prompt in `scraper/enricher.py` tells Claude about the target user:

> Senior Technical Business Analyst / Integration Analyst with 10+ years experience across NZ government, health, and banking sectors. Key skills: API design, integration architecture, AWS, Azure, Salesforce, data migration, requirements analysis, stakeholder management.

Claude uses this to score each tender from 0-100. A tender for a large health system integration using Azure and APIs will score in the 80s or 90s. A tender for website design will score in the teens. The dashboard treats 70+ as "high relevance" and tracks it as a headline metric.

**To change the profile**, edit the `ENRICHMENT_PROMPT` string in `scraper/enricher.py`. Rewrite the user description to match your own background. Future scrape runs will score against the new profile. Existing tenders keep their old scores.

---

## Database details

### Tables

**`tenders`** — one row per tender. Raw fields from GETS (title, agency, closing date, description, URL, type, value, status) plus AI enrichment fields (tech stack, roles, programme size, relevance score, reasoning, Seek timeline, themes). Keyed on `gets_url` which has a unique constraint.

**`tender_scrape_runs`** — one row per scraper execution. Tracks when it ran, how many tenders it found, how many were new, and any errors.

### Views

These are PostgreSQL views that auto-aggregate from the tenders table. The dashboard queries them directly — no application-level aggregation needed.

- **`agency_activity`** — tender count, open count, and average relevance per agency
- **`tech_trends`** — how many tenders mention each technology (uses `unnest` on the tech stack array)
- **`role_demand`** — how many tenders will need each role, with average relevance
- **`theme_summary`** — count of tenders per theme

### Security

Row Level Security is enabled. Both tables allow public reads (so the dashboard works with the anon key) and restrict writes to authenticated requests (the service role key, used by the scraper).

---

## Customising GovRadar

### Change what gets scraped

Edit `TARGET_KEYWORDS` in `scraper/gets_scraper.py` to widen or narrow the filter. Edit `max_pages` in `scraper/run.py` to control how deep into GETS the scraper goes (default: 11 pages = ~275 tenders).

### Change the AI profile

Edit `ENRICHMENT_PROMPT` in `scraper/enricher.py`. Rewrite the user description. A data engineer's profile will produce very different scores from a project manager's.

### Change the AI model

The model is set in `scraper/enricher.py` — currently `claude-sonnet-4-20250514`. You could swap to a different Claude model. Faster models cost less but may produce less nuanced analysis.

### Change the schedule

Edit the cron expression in `.github/workflows/scrape.yml`. Default is `30 18 * * *` (UTC), which is ~7:30am NZST. Set it to `30 18 * * 1-5` for weekdays only, or `0 6,18 * * *` for twice daily.

### Change the dashboard

Edit `app.py`. It's standard Streamlit — `st.tabs()` for navigation, `st.dataframe()` for tables, `st.bar_chart()` for charts, `st.expander()` for detail cards. Add new tabs, change the layout, adjust what columns show up. The top 20 tenders get expandable detail cards; change `df.head(20)` if you want more or fewer.

### Add a new field to the analysis

1. Add a column in Supabase: `alter table tenders add column new_field text;`
2. Update `setup/schema.sql` so fresh installs include it
3. Add the field to the Claude prompt in `scraper/enricher.py` and parse it from the response
4. Display it in `app.py`

---

## How GETS works (for context)

GETS ([gets.govt.nz](https://www.gets.govt.nz)) is the NZ government's official procurement portal. When a government agency wants to buy something — whether it's a $50 million IT transformation or a box of pens — they post a tender on GETS. Suppliers respond through the platform.

Tender types you'll see:
- **RFP** (Request for Proposal) — "we want to buy this, tell us how you'd do it and what it would cost"
- **RFI** (Request for Information) — "we're thinking about buying something, tell us what's possible"
- **ROI** (Registration of Interest) — "we might need something, raise your hand if you're interested"
- **EOI** (Expression of Interest) — similar to ROI
- **RFQ** (Request for Quotation) — "give us a price for this specific thing"

For contractors, the important ones are RFPs and RFIs — they signal real programmes that will need people. ROIs and EOIs are earlier in the pipeline but still worth tracking.

The scraper navigates GETS listing pages at `https://www.gets.govt.nz/ExternalIndex.htm` (paginated with `?page=N`), then follows each tender's link to its detail page at `https://www.gets.govt.nz/{ORG_CODE}/ExternalTenderDetails.htm?id={NUMERIC_ID}` to get the full description.

---

## Running costs

This is designed to be cheap or free to run:

| Component | Cost |
|---|---|
| Supabase | Free tier (plenty for this use case) |
| Streamlit Cloud | Free for public apps |
| GitHub Actions | Free for public repos |
| Claude API | ~$0.10 to $1.50 per daily run, depending on how many relevant tenders are found |

The only real cost is the Anthropic API. A month of daily runs typically costs $3-$45 depending on how active the tender pipeline is.

---

## Troubleshooting

**"SUPABASE_URL and SUPABASE_KEY must be set"** — your environment variables aren't loaded. Check `.env` exists locally, or check GitHub secrets for Actions.

**Scraper finds 0 tenders** — either GETS is down, their HTML structure changed (check the table class name `contentTable` in `gets_scraper.py`), or the keywords are too narrow.

**Dashboard shows nothing** — run the scraper at least once. Check Supabase Table Editor to see if data is there. Make sure the key you're using has read access.

**"Failed to parse Claude response"** — Claude occasionally produces malformed JSON. The enricher handles this gracefully by recording a relevance score of 0 with "Enrichment failed" as the reasoning. It won't crash the run.

**GitHub Actions not triggering** — make sure the workflow file is on the `main` branch, secrets are set, and note that GitHub cron schedules can have up to 15 minutes of delay.

**Permission errors on insert/update** — you're probably using the anon key instead of the service role key. The scraper needs write access.

---

## What's next

Things that would make this better but aren't built yet:

- **PDF parsing** — many tenders attach full RFP documents as PDFs. Parsing those would give the AI much more to work with and produce better analysis.
- **Alerts** — email or Slack notification when a tender scoring 80+ appears.
- **Trend tracking** — how is agency spending changing month over month? Are health tenders increasing? Is cloud adoption accelerating?
- **Advanced GETS search** — instead of keyword matching, use the GETS advanced search form to filter by UNSPSC procurement categories directly.
- **Re-scoring** — when you change your profile, re-run the AI on existing tenders so historical scores reflect your current priorities.
- **Status monitoring** — track when open tenders get awarded or cancelled, and who won them.

---

## Relationship to ContractRadar

GovRadar shares a Supabase project with [ContractRadar](https://github.com/phili/ContractRadar) (same database, different tables) and follows the same patterns — singleton database client, similar query layer, same deployment approach. ContractRadar watches the *demand* side (job listings on Seek), while GovRadar watches the *supply* side (government tenders on GETS). Together they give you both sides of the equation: what's being tendered now, and what roles are being hired for.
