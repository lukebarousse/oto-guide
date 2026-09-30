-- Incremental changes for an existing project (run in the Supabase SQL editor).
-- schema.sql already includes all of these for a fresh install.
-- Every statement is idempotent — safe to re-run the whole file.

-- 2026-08: admin 🎯 target finish per race (drives suggested waves)
alter table seasons add column if not exists target_finish_205 text;
alter table seasons add column if not exists target_finish_65  text;

-- 2026-09: bathrooms per exchange zone live with the other course facts in
-- builder/data.py (ZONE_BATHROOMS), not the database. Clean up the short-lived
-- attempts at storing them here:
drop table if exists zones;
alter table legs drop column if exists bathroom;
