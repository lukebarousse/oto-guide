-- OTO Guide schema. Run this once in the Supabase SQL editor, then run seed_legs.sql.
-- Security model (deliberate, per the race's needs):
--   * everything is publicly readable
--   * team-scoped tables (teams/runners/assignments) are publicly WRITABLE —
--     team pages are capability URLs by slug; acceptable for roster/pace data
--   * seasons + legs content are admin-only writes (Supabase Auth; disable public
--     signups in Auth settings — you and JT are created by hand in the dashboard)

create table seasons (
  id    serial primary key,
  year  int not null unique,
  active boolean not null default false
);

create table teams (
  id         uuid primary key default gen_random_uuid(),
  season_id  int not null references seasons(id) on delete cascade,
  race       text not null default '205' check (race in ('205','65')),
  slug       text not null,
  name       text not null,
  n_runners  int not null default 6 check (n_runners between 1 and 12),
  pace_min_per_mi numeric(4,2) not null default 10.0,
  wave_start text,                        -- "HH:MM", assigned by the race director
  notes      text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (season_id, slug)
);

create table runners (
  team_id uuid not null references teams(id) on delete cascade,
  slot    int not null check (slot between 1 and 12),
  name    text not null default '',
  pace_min_per_mi numeric(4,2),           -- optional per-runner pace override
  primary key (team_id, slot)
);

-- leg -> slot; seeded by rotation, editable per leg by the team
create table assignments (
  team_id uuid not null references teams(id) on delete cascade,
  leg     int not null check (leg between 1 and 36),
  slot    int not null check (slot between 1 and 12),
  primary key (team_id, leg)
);

-- per-season leg content (admin-editable wording + flags)
create table legs (
  season_id int not null references seasons(id) on delete cascade,
  n         int not null check (n between 1 and 36),
  beta      text not null default '',
  tags      jsonb not null default '[]',
  team_rating text,                        -- community-adjusted rating shown as "team says"
  surface_text text not null default '',
  primary key (season_id, n)
);

alter table seasons     enable row level security;
alter table teams       enable row level security;
alter table runners     enable row level security;
alter table assignments enable row level security;
alter table legs        enable row level security;

-- public read on everything
create policy pub_read_seasons     on seasons     for select using (true);
create policy pub_read_teams       on teams       for select using (true);
create policy pub_read_runners     on runners     for select using (true);
create policy pub_read_assignments on assignments for select using (true);
create policy pub_read_legs        on legs        for select using (true);

-- team-scoped tables: open writes (capability-URL model), but no team create/delete
create policy pub_update_teams  on teams       for update using (true) with check (true);
create policy pub_all_runners   on runners     for all    using (true) with check (true);
create policy pub_all_assign    on assignments for all    using (true) with check (true);

-- admin-only (any authenticated user; signups disabled so that's just you + JT)
create policy adm_all_seasons on seasons for all to authenticated using (true) with check (true);
create policy adm_ins_teams   on teams   for insert to authenticated with check (true);
create policy adm_del_teams   on teams   for delete to authenticated using (true);
create policy adm_all_legs    on legs    for all to authenticated using (true) with check (true);

-- first season
insert into seasons (year, active) values (2026, true);
