-- GovRadar schema — run in Supabase SQL Editor
-- Same project as ContractRadar, different tables

-- Tender scrape run tracking
create table if not exists tender_scrape_runs (
    id uuid primary key default gen_random_uuid(),
    run_date timestamptz not null default now(),
    tenders_found int not null default 0,
    tenders_new int not null default 0,
    errors text
);

-- Main tenders table
create table if not exists tenders (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    agency text,
    closing_date date,
    category text,
    description text,
    gets_url text unique not null,
    tender_type text,                          -- RFP / RFI / ROI / EOI
    estimated_value text,
    status text not null default 'open',        -- open / closed
    date_scraped timestamptz not null default now(),
    -- AI enrichment fields
    probable_tech_stack text[] default '{}',
    probable_roles text[] default '{}',
    programme_size text,                        -- small / medium / large / mega
    relevance_score int default 0,              -- 0-100
    relevance_reasoning text,
    estimated_seek_timeline text,               -- 3 / 6 / 9 / 12 months
    themes text[] default '{}',
    scrape_run_id uuid references tender_scrape_runs(id)
);

-- Indexes
create index if not exists idx_tenders_relevance on tenders(relevance_score desc);
create index if not exists idx_tenders_closing on tenders(closing_date);
create index if not exists idx_tenders_agency on tenders(agency);
create index if not exists idx_tenders_status on tenders(status);
create index if not exists idx_tenders_date_scraped on tenders(date_scraped desc);

-- Views
create or replace view agency_activity as
select
    agency,
    count(*) as tender_count,
    count(*) filter (where status = 'open') as open_count,
    avg(relevance_score) as avg_relevance
from tenders
group by agency
order by tender_count desc;

create or replace view theme_summary as
select
    unnest(themes) as theme,
    count(*) as mention_count
from tenders
group by theme
order by mention_count desc;

create or replace view role_demand as
select
    unnest(probable_roles) as role,
    count(*) as demand_count,
    avg(relevance_score) as avg_relevance
from tenders
group by role
order by demand_count desc;

create or replace view tech_trends as
select
    unnest(probable_tech_stack) as technology,
    count(*) as mention_count
from tenders
group by technology
order by mention_count desc;

-- RLS
alter table tenders enable row level security;
alter table tender_scrape_runs enable row level security;

create policy "Allow public read on tenders"
    on tenders for select using (true);

create policy "Allow service insert on tenders"
    on tenders for insert with check (true);

create policy "Allow service update on tenders"
    on tenders for update using (true);

create policy "Allow public read on tender_scrape_runs"
    on tender_scrape_runs for select using (true);

create policy "Allow service insert on tender_scrape_runs"
    on tender_scrape_runs for insert with check (true);

create policy "Allow service update on tender_scrape_runs"
    on tender_scrape_runs for update using (true);
