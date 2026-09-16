-- PolicyCrab case management: track a claim through the appeal lifecycle inside
-- a team workspace (or personally): owner, assignee, status, priority, due date,
-- and an activity log. Requires 009 (organizations) and 002 (user_claims).
--
-- One case per claim. Free-text fields (notes, comments) are PHI-scrubbed by the
-- backend before they are stored. Inert until CASES_ENABLED=true.

create extension if not exists pgcrypto;

create table if not exists public.cases (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references public.organizations(id) on delete cascade,      -- NULL = personal case
  claim_id uuid not null references public.user_claims(id) on delete cascade,
  created_by uuid not null references auth.users(id) on delete cascade,
  assignee_id uuid references auth.users(id) on delete set null,
  title text not null check (char_length(title) between 1 and 140),
  status text not null default 'new'
    check (status in ('new', 'in_review', 'appeal_filed', 'awaiting_decision', 'won', 'partial', 'lost', 'withdrawn')),
  priority text not null default 'normal' check (priority in ('low', 'normal', 'high', 'urgent')),
  due_date date,
  amount_at_stake numeric,
  reference text,                                                          -- internal case number; never PHI
  notes text,                                                              -- PHI-scrubbed
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  closed_at timestamptz,
  unique (claim_id)
);

create index if not exists idx_cases_org_status on public.cases (org_id, status);
create index if not exists idx_cases_org_assignee on public.cases (org_id, assignee_id);
create index if not exists idx_cases_org_due on public.cases (org_id, due_date);
create index if not exists idx_cases_created_by on public.cases (created_by);

create table if not exists public.case_events (
  id uuid primary key default gen_random_uuid(),
  case_id uuid not null references public.cases(id) on delete cascade,
  org_id uuid,
  actor_id uuid,
  actor_email text,
  event_type text not null,      -- created | status_changed | assigned | priority_changed | due_date_changed
                                 -- | notes_updated | comment | outcome_recorded
  message text,                  -- PHI-scrubbed
  data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_case_events_case_created on public.case_events (case_id, created_at desc);

-- ── Row Level Security (defence in depth; the API enforces access in Python) ──

alter table public.cases enable row level security;
alter table public.case_events enable row level security;

drop policy if exists "Members can read cases" on public.cases;
create policy "Members can read cases"
  on public.cases for select
  using (created_by = auth.uid() or (org_id is not null and public.is_org_member(org_id)));

drop policy if exists "Members can read case events" on public.case_events;
create policy "Members can read case events"
  on public.case_events for select
  using (exists (
    select 1 from public.cases c
    where c.id = case_events.case_id
      and (c.created_by = auth.uid() or (c.org_id is not null and public.is_org_member(c.org_id)))
  ));

grant all on table public.cases to service_role;
grant all on table public.case_events to service_role;
grant select on table public.cases to authenticated;
grant select on table public.case_events to authenticated;
