-- Incremental changes for an existing project (run in the Supabase SQL editor).
-- schema.sql already includes all of these for a fresh install.
-- Every statement is idempotent — safe to re-run the whole file.

-- 2026-08: admin 🎯 target finish per race (drives suggested waves)
alter table seasons add column if not exists target_finish_205 text;
alter table seasons add column if not exists target_finish_65  text;

-- 2026-09: bathrooms per exchange zone (zone k = end of leg k = start of leg k+1;
-- 0 = start line, 36 = finish). Shown on each leg card's Start / End line.
create table if not exists zones (
  season_id int not null references seasons(id) on delete cascade,
  zone      int not null check (zone between 0 and 36),
  bathroom  boolean,                        -- null = unknown, true = 🚻, false = 🚫
  primary key (season_id, zone)
);
alter table zones enable row level security;
drop policy if exists pub_read_zones on zones;
create policy pub_read_zones on zones for select using (true);
drop policy if exists adm_all_zones on zones;
create policy adm_all_zones on zones for all to authenticated using (true) with check (true);
-- (a short-lived legs.bathroom column was never used; harmless if you added it)
alter table legs drop column if exists bathroom;
