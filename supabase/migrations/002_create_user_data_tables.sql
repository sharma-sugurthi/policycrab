-- PolicyCrab user data tables.
-- These replace the local SQLAlchemy/SQLite user history path.

create extension if not exists pgcrypto;

create table if not exists public.user_policies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id text,
  policy_profile_json jsonb not null,
  created_at timestamptz not null default now()
);

alter table public.user_policies
  add column if not exists session_id text;

create index if not exists idx_user_policies_user_created
  on public.user_policies (user_id, created_at desc);

create table if not exists public.user_claims (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  policy_id uuid references public.user_policies(id) on delete set null,
  claim_description text not null,
  cost_breakdown_json jsonb,
  appeal_output_json jsonb,
  route_decision text,
  created_at timestamptz not null default now()
);

create index if not exists idx_user_claims_user_created
  on public.user_claims (user_id, created_at desc);

alter table public.user_policies enable row level security;
alter table public.user_claims enable row level security;

drop policy if exists "Users can read their policies" on public.user_policies;
create policy "Users can read their policies"
  on public.user_policies for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their policies" on public.user_policies;
create policy "Users can insert their policies"
  on public.user_policies for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can read their claims" on public.user_claims;
create policy "Users can read their claims"
  on public.user_claims for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their claims" on public.user_claims;
create policy "Users can insert their claims"
  on public.user_claims for insert
  with check (auth.uid() = user_id);

-- ── Raw text column (added post-launch) ───────────────────────────
-- Stores the first ~5 KB of the original raw SBC/policy text so the document
-- can be audited or re-extracted without the user needing to re-upload.
alter table public.user_policies
  add column if not exists raw_text text;

-- ── Service-role grants ──────────────────────────────────────────────
-- These were applied to the live database by the Replit provisioner but were
-- omitted from the published migration files. Without them the backend's
-- service-role Supabase client cannot INSERT/SELECT from either table.
GRANT ALL ON TABLE public.user_policies TO service_role;
GRANT ALL ON TABLE public.user_claims   TO service_role;
