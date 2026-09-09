-- PolicyCrab appeal outcome tracking.
--
-- Records what actually happened to an appeal (won / partial / lost / pending /
-- withdrawn) against the prediction the pipeline made at drafting time. This is
-- the data source for calibrating the deterministic success score and for the
-- honest "X% of appeals overturned" number.
--
-- Design notes:
--   * One outcome per claim (unique claim_id); re-recording upserts.
--   * Prediction fields are SNAPSHOTTED at record time. Recomputing them later
--     with a newer scorer version would corrupt the calibration data.
--   * org_id is reserved (nullable) for future team workspaces; no FK yet.
--   * Contains no PHI — deliberately NOT included in purge_hipaa_records_after_30_days().
-- Follows the security patterns of 002/005 (RLS on auth.uid(), service_role grants).

create extension if not exists pgcrypto;

create table if not exists public.appeal_outcomes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  org_id uuid,
  claim_id uuid not null references public.user_claims(id) on delete cascade,
  outcome text not null check (outcome in ('won', 'partial', 'lost', 'pending', 'withdrawn')),
  amount_recovered numeric,
  amount_at_stake numeric,
  appeal_level integer,
  decided_at date,
  notes text,
  -- prediction snapshot (copied from user_claims.appeal_output_json at record time)
  predicted_success_score numeric,
  predicted_band text,
  predicted_probability_llm numeric,
  score_version text,
  recorded_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (claim_id)
);

create index if not exists idx_appeal_outcomes_user_recorded
  on public.appeal_outcomes (user_id, recorded_at desc);
create index if not exists idx_appeal_outcomes_outcome
  on public.appeal_outcomes (outcome);

alter table public.appeal_outcomes enable row level security;

drop policy if exists "Users can read their outcomes" on public.appeal_outcomes;
create policy "Users can read their outcomes"
  on public.appeal_outcomes for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their outcomes" on public.appeal_outcomes;
create policy "Users can insert their outcomes"
  on public.appeal_outcomes for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can update their outcomes" on public.appeal_outcomes;
create policy "Users can update their outcomes"
  on public.appeal_outcomes for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete their outcomes" on public.appeal_outcomes;
create policy "Users can delete their outcomes"
  on public.appeal_outcomes for delete
  using (auth.uid() = user_id);

GRANT ALL ON TABLE public.appeal_outcomes TO service_role;
