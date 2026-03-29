-- Optional hardening for private deployments.
-- Run this after setup/schema.sql if the dashboard should not be publicly readable.
-- After applying this, configure the Streamlit app with SUPABASE_SERVICE_ROLE_KEY
-- instead of a publishable/anon key, or introduce Supabase Auth and custom policies.

revoke select on tenders from anon, authenticated;
revoke select on tender_scrape_runs from anon, authenticated;
revoke select on agency_activity from anon, authenticated;
revoke select on tech_trends from anon, authenticated;
revoke select on role_demand from anon, authenticated;
revoke select on theme_summary from anon, authenticated;

drop policy if exists "Allow public read on tenders" on tenders;
drop policy if exists "Allow public read on tender_scrape_runs" on tender_scrape_runs;

create policy "Allow private dashboard read on tenders"
    on tenders
    for select
    to service_role
    using (true);

create policy "Allow private dashboard read on tender_scrape_runs"
    on tender_scrape_runs
    for select
    to service_role
    using (true);
