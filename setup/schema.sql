-- GovRadar schema. Run this in the Supabase SQL Editor.
-- Same project as ContractRadar, different tables.

create extension if not exists pgcrypto;

create table if not exists tender_scrape_runs (
    id uuid primary key default gen_random_uuid(),
    run_date timestamptz not null default now(),
    tenders_found int not null default 0,
    tenders_new int not null default 0,
    high_relevance_found int not null default 0,
    closing_soon_count int not null default 0,
    summary text,
    errors text
);

create table if not exists tenders (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    agency text,
    closing_date date,
    category text,
    description text,
    gets_url text unique not null,
    tender_type text,
    estimated_value text,
    status text not null default 'open',
    date_scraped timestamptz not null default now(),
    probable_tech_stack text[] not null default '{}',
    probable_roles text[] not null default '{}',
    programme_size text,
    relevance_score int not null default 0,
    relevance_reasoning text,
    estimated_seek_timeline text,
    themes text[] not null default '{}',
    scrape_run_id uuid references tender_scrape_runs(id)
);

alter table tenders
    add column if not exists rfx_id text,
    add column if not exists attachment_urls text[] not null default '{}',
    add column if not exists attachment_text_excerpt text,
    add column if not exists first_seen_at timestamptz not null default now(),
    add column if not exists last_seen_at timestamptz not null default now(),
    add column if not exists enrichment_model text,
    add column if not exists enrichment_prompt_version text,
    add column if not exists enrichment_updated_at timestamptz;

alter table tender_scrape_runs
    add column if not exists high_relevance_found int not null default 0,
    add column if not exists closing_soon_count int not null default 0,
    add column if not exists summary text;

alter table tenders
    drop constraint if exists tenders_status_check,
    drop constraint if exists tenders_programme_size_check,
    drop constraint if exists tenders_relevance_score_check,
    drop constraint if exists tenders_estimated_seek_timeline_check;

alter table tenders
    add constraint tenders_status_check
        check (status in ('open', 'closed')),
    add constraint tenders_programme_size_check
        check (programme_size is null or programme_size in ('small', 'medium', 'large', 'mega')),
    add constraint tenders_relevance_score_check
        check (relevance_score between 0 and 100),
    add constraint tenders_estimated_seek_timeline_check
        check (
            estimated_seek_timeline is null
            or estimated_seek_timeline in ('3 months', '6 months', '9 months', '12 months')
        );

create index if not exists idx_tenders_relevance on tenders(relevance_score desc);
create index if not exists idx_tenders_closing on tenders(closing_date);
create index if not exists idx_tenders_agency on tenders(agency);
create index if not exists idx_tenders_status on tenders(status);
create index if not exists idx_tenders_date_scraped on tenders(date_scraped desc);
create index if not exists idx_tenders_first_seen on tenders(first_seen_at desc);
create index if not exists idx_tenders_last_seen on tenders(last_seen_at desc);

create or replace view agency_activity
with (security_invoker = true) as
select
    agency,
    count(*) as tender_count,
    count(*) filter (where status = 'open') as open_count,
    avg(relevance_score) as avg_relevance
from tenders
where agency is not null and agency <> ''
group by agency
order by tender_count desc;

create or replace view theme_summary
with (security_invoker = true) as
select
    unnest(themes) as theme,
    count(*) as mention_count
from tenders
group by theme
order by mention_count desc;

create or replace view role_demand
with (security_invoker = true) as
select
    unnest(probable_roles) as role,
    count(*) as demand_count,
    avg(relevance_score) as avg_relevance
from tenders
group by role
order by demand_count desc;

create or replace view tech_trends
with (security_invoker = true) as
select
    unnest(probable_tech_stack) as technology,
    count(*) as mention_count
from tenders
group by technology
order by mention_count desc;

revoke all on tenders from public;
revoke all on tender_scrape_runs from public;
revoke all on agency_activity from public;
revoke all on theme_summary from public;
revoke all on role_demand from public;
revoke all on tech_trends from public;

grant usage on schema public to anon, authenticated, service_role;

revoke all on tenders from anon, authenticated;
revoke all on tender_scrape_runs from anon, authenticated;
revoke all on agency_activity from anon, authenticated;
revoke all on theme_summary from anon, authenticated;
revoke all on role_demand from anon, authenticated;
revoke all on tech_trends from anon, authenticated;

grant select on tenders to anon, authenticated, service_role;
grant insert, update on tenders to service_role;

grant select on tender_scrape_runs to anon, authenticated, service_role;
grant insert, update on tender_scrape_runs to service_role;

grant select on agency_activity to anon, authenticated, service_role;
grant select on theme_summary to anon, authenticated, service_role;
grant select on role_demand to anon, authenticated, service_role;
grant select on tech_trends to anon, authenticated, service_role;

alter table tenders enable row level security;
alter table tender_scrape_runs enable row level security;

drop policy if exists "Allow public read on tenders" on tenders;
drop policy if exists "Allow service insert on tenders" on tenders;
drop policy if exists "Allow service update on tenders" on tenders;
drop policy if exists "Allow public read on tender_scrape_runs" on tender_scrape_runs;
drop policy if exists "Allow service insert on tender_scrape_runs" on tender_scrape_runs;
drop policy if exists "Allow service update on tender_scrape_runs" on tender_scrape_runs;

create policy "Allow public read on tenders"
    on tenders
    for select
    using (true);

create policy "Allow service insert on tenders"
    on tenders
    for insert
    to service_role
    with check (true);

create policy "Allow service update on tenders"
    on tenders
    for update
    to service_role
    using (true);

create policy "Allow public read on tender_scrape_runs"
    on tender_scrape_runs
    for select
    using (true);

create policy "Allow service insert on tender_scrape_runs"
    on tender_scrape_runs
    for insert
    to service_role
    with check (true);

create policy "Allow service update on tender_scrape_runs"
    on tender_scrape_runs
    for update
    to service_role
    using (true);
