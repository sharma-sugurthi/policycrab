-- appeal_deadlines: the deadline tracker used by /api/deadlines.
--
-- Until now this table existed only in the live database (created by hand),
-- so a fresh environment could not be provisioned from the migrations alone.
-- This file makes it reproducible and is idempotent: on a database that already
-- has the table it only adds any missing columns/policies.
--
-- Note on access control: the backend reaches Postgres with the service role,
-- so the RLS below protects direct PostgREST access only. Ownership checks for
-- the API live in app/api/deadline_routes.py (every query filters by user_id).

create extension if not exists pgcrypto;

create table if not exists public.appeal_deadlines (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  carrier_name text not null,
  appeal_level text not null,
  appeal_framework text not null,
  state_code text not null,
  date_denial_received date not null,
  date_appeal_filed date,
  deadline_date date not null,
  statutory_days integer not null,
  insurer_response_deadline date,
  insurer_response_days integer,
  status text not null default 'pending',
  notes text,
  claim_summary text,
  created_at timestamptz not null default now()
);

-- Converge older hand-made copies of the table (all nullable so existing rows are fine).
alter table public.appeal_deadlines add column if not exists date_appeal_filed date;
alter table public.appeal_deadlines add column if not exists insurer_response_deadline date;
alter table public.appeal_deadlines add column if not exists insurer_response_days integer;
alter table public.appeal_deadlines add column if not exists status text default 'pending';
alter table public.appeal_deadlines add column if not exists notes text;
alter table public.appeal_deadlines add column if not exists claim_summary text;
alter table public.appeal_deadlines add column if not exists created_at timestamptz default now();

create index if not exists idx_appeal_deadlines_user_deadline
  on public.appeal_deadlines (user_id, deadline_date);

alter table public.appeal_deadlines enable row level security;

-- ::text casts keep these valid whether user_id is uuid or a legacy text column.
drop policy if exists "Users can read their deadlines" on public.appeal_deadlines;
create policy "Users can read their deadlines"
  on public.appeal_deadlines for select using (auth.uid()::text = user_id::text);

drop policy if exists "Users can insert their deadlines" on public.appeal_deadlines;
create policy "Users can insert their deadlines"
  on public.appeal_deadlines for insert with check (auth.uid()::text = user_id::text);

drop policy if exists "Users can update their deadlines" on public.appeal_deadlines;
create policy "Users can update their deadlines"
  on public.appeal_deadlines for update using (auth.uid()::text = user_id::text);

drop policy if exists "Users can delete their deadlines" on public.appeal_deadlines;
create policy "Users can delete their deadlines"
  on public.appeal_deadlines for delete using (auth.uid()::text = user_id::text);

grant all on table public.appeal_deadlines to service_role;
