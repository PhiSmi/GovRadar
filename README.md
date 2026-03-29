# GovRadar

GovRadar is a tender intelligence product for tracking New Zealand government technology work before it turns into downstream hiring.

It watches the Government Electronic Tenders Service (GETS), pulls out tenders that look relevant to digital, software, integration, cloud, health, and professional-services delivery, enriches them with AI, and presents the result in a Streamlit dashboard backed by Supabase.

The purpose is straightforward: GETS is where the work starts. Recruiters and job boards show up later. GovRadar helps close that gap.

## Why it exists

By the time a contract role appears in market, the underlying programme is usually already underway. The tender may have been published months earlier. That means there is a window where the market signal already exists, but it is still buried inside procurement data.

GovRadar is built to surface that signal earlier and make it usable.

Instead of manually scanning GETS and guessing what each tender means, the dashboard tries to answer the questions that are usually more valuable than the raw listing itself:

- Which agencies are actually active right now?
- What kind of delivery work are they likely buying?
- Which roles and technology stacks are implied by the tender?
- How relevant is this to a specific contractor or consulting profile?
- When is that work likely to turn into delivery teams and hiring demand?

## Primary use cases

GovRadar works well for:

- Independent contractors looking for early market visibility.
- Consultants and practice leads tracking agency activity and likely delivery demand.
- People planning what to upskill in based on real procurement patterns.
- Anyone who wants a structured, searchable view of the public-sector delivery pipeline.

The default enrichment prompt is tuned for a senior Technical BA / Integration Analyst profile, but that prompt is editable and the scoring model can be retargeted to other roles.

## Product shape

The dashboard has seven working views:

- `Overview`
  A market snapshot with top opportunities, closings soon, hiring-window distribution, and relevance distribution.
- `Pipeline`
  The main tender explorer with search, filters, export, and detailed tender drill-downs.
- `Agencies`
  Agency activity ranked by tender count, open count, and average relevance.
- `Tech`
  Technology mentions extracted from enriched tenders.
- `Roles`
  Likely downstream role demand inferred from tender descriptions.
- `Timeline`
  Expected timing for when work from a tender is likely to turn into delivery and hiring.
- `Themes`
  Common programme patterns such as migration, integration, modernisation, or regulatory work.

## How it works

GovRadar has four parts.

### 1. GETS scraper

`scraper/gets_scraper.py`

The scraper walks GETS listing pages, follows tender detail links, and keeps tenders that match a configurable keyword set. It is designed for the public GETS HTML interface rather than browser automation, so the implementation stays lightweight and easy to maintain.

### 2. AI enrichment

`scraper/enricher.py`

Each relevant tender is sent to Anthropic for structured analysis. The model returns:

- probable tech stack
- probable delivery roles
- programme size
- relevance score
- one-line reasoning
- expected hiring window
- themes

If the enrichment call fails or returns malformed JSON, the run falls back to a safe default payload rather than crashing the entire pipeline.

### 3. Supabase storage

`db/`

Supabase stores the tender records, scrape history, and reporting views. The app uses the Supabase REST API directly via `requests`, which keeps the dependency surface small and avoids needing the heavier Python SDK for this use case.

### 4. Streamlit dashboard

`app.py`

The dashboard reads from Supabase, applies search and filter logic, and renders the product views.

## Repository layout

```text
GovRadar/
|-- app.py
|-- requirements.txt
|-- .python-version
|-- .env.example
|-- db/
|   |-- client.py
|   `-- queries.py
|-- scraper/
|   |-- gets_scraper.py
|   |-- enricher.py
|   `-- run.py
|-- setup/
|   |-- schema.sql
|   `-- private_dashboard.sql
|-- .streamlit/
|   `-- config.toml
`-- .github/
    `-- workflows/
        `-- scrape.yml
```

## Environment variables

GovRadar supports separate read and write keys.

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-publishable-or-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-or-secret-key
ANTHROPIC_API_KEY=your-anthropic-key
```

Notes:

- The dashboard only needs a read-capable key in the default public-read setup.
- The scraper requires a write-capable key.
- `SUPABASE_KEY` is still supported as a legacy fallback.
- Local `.env` files are loaded automatically.

## Python version

Use Python 3.11.

The repo is pinned for Python 3.11 in automation, and that is the safest target for local development as well.

## Database model

GovRadar creates:

- `tenders`
- `tender_scrape_runs`
- `agency_activity`
- `tech_trends`
- `role_demand`
- `theme_summary`

The `tenders` table stores both the raw procurement fields and the AI enrichment fields. `gets_url` is used as the upsert key so repeated runs do not duplicate the same tender.

The schema also adds:

- indexes for the main dashboard filters
- value constraints for status, programme size, relevance score, and timeline values
- explicit grants and RLS policies

## Security model

There are two supported operating modes.

### Default mode: public read, private write

Run `setup/schema.sql`.

This mode is designed for a read-only public dashboard:

- `anon` and `authenticated` can read the reporting data
- only `service_role` can insert or update
- Streamlit can run with a publishable key
- the scraper uses the service role key

This is appropriate if the dataset is intended to be publicly readable through the app and there is no sensitivity around exposing the tender/enrichment data to anyone who has the Supabase project URL and read key.

### Private dashboard mode

Run `setup/schema.sql`, then run `setup/private_dashboard.sql`.

This mode revokes `anon` and `authenticated` read access from the tables and views. It is the stricter option if the dashboard should not be publicly queryable through the Supabase REST API.

If you enable private dashboard mode:

- do not use a publishable key in Streamlit
- configure the Streamlit app with `SUPABASE_SERVICE_ROLE_KEY`
- keep the app itself private or access-controlled

The repo supports that configuration already. If no read key is present, the app can read through the service role key server-side.

## Local setup

### 1. Create the schema

Open Supabase SQL Editor and run:

- `setup/schema.sql`

Optional:

- `setup/private_dashboard.sql` if you want a private dashboard deployment

### 2. Configure secrets

Copy the example file:

```bash
cp .env.example .env
```

Fill in your real values.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the scraper

```bash
python -m scraper.run
```

What should happen:

1. A scrape-run row is created.
2. GETS listing and detail pages are fetched.
3. Matching tenders are enriched with Anthropic.
4. Results are upserted into Supabase.

If the write-capable Supabase key is missing, the scraper now fails clearly instead of silently trying to run with a publishable key.

### 5. Launch the dashboard

```bash
streamlit run app.py
```

## Deployment

### Streamlit Community Cloud

Default public-read deployment:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-publishable-or-anon-key"
```

Private deployment:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "your-service-role-or-secret-key"
```

For a private deployment, the app itself should also be access-controlled.

### GitHub Actions

The workflow in `.github/workflows/scrape.yml` uses two UTC cron entries and a timezone guard so the scraper targets 7:30am Auckland time across DST changes.

Recommended GitHub repository secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY`

Legacy fallback:

- `SUPABASE_KEY`

## Dashboard features

The current app includes:

- full-text search across title, agency, category, description, and enrichment fields
- minimum relevance filtering
- agency and category filters
- optional 70+ relevance view
- multiple sort modes
- CSV export for the filtered result set
- spotlight cards for top opportunities
- structured tender detail drill-downs
- scrape freshness and recent-run visibility

## Tuning and customisation

### Adjust relevance filtering

Edit `TARGET_KEYWORDS` in `scraper/gets_scraper.py`.

### Change the target user profile

Edit `ENRICHMENT_PROMPT` in `scraper/enricher.py`.

### Change scrape depth

Edit `max_pages` in `scraper/run.py`.

### Change the model

Edit the model name in `scraper/enricher.py`.

### Change the dashboard theme

Adjust:

- `.streamlit/config.toml`
- the CSS block in `app.py`

## Operational notes

- GETS structure can change. The scraper includes fallback table detection, but the site should be checked if results suddenly drop to zero.
- The enrichment pipeline is only as good as the text available in the tender description. PDF attachment parsing is not implemented yet.
- Existing tenders are not automatically re-scored if the prompt/profile changes.
- The dashboard is read-only by design. All writes happen in the scraper path.

## Troubleshooting

### "Could not find the table 'public.tenders' in the schema cache"

The app can reach Supabase, but the GovRadar schema is missing in the connected project or the app is pointed at the wrong project.

Check:

1. `setup/schema.sql` was run in the same Supabase project referenced by `SUPABASE_URL`
2. the `public.tenders` table exists
3. the app is using the expected project URL and key

### The dashboard loads but shows no data

Usually one of these is true:

- the schema exists but the scraper has not run yet
- filters are excluding all rows
- the app is pointed at the wrong project

### "A write-capable Supabase key must be set for the scraper"

The scraper is running with a read-only key. Set `SUPABASE_SERVICE_ROLE_KEY`.

### Anthropic enrichment fails

GovRadar stores a fallback enrichment payload and continues. Inspect logs to see whether the issue is rate limiting, malformed output, or key/configuration related.

## Current limits

GovRadar is already useful, but it is still a focused v1 product.

Not built yet:

- PDF attachment extraction
- alerting or notifications
- historical trend baselining
- re-scoring historical tenders after prompt changes
- automated test coverage
- migration tooling beyond the bootstrap SQL scripts

## In practice

When the system is working properly:

1. the scraper runs on schedule
2. tenders land in `public.tenders`
3. the dashboard shows ranked opportunities with market summaries
4. agencies, technology patterns, and likely role demand become visible before the hiring wave does
