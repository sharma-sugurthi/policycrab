-- PolicyCrab usage metering and append-only audit trail.
--
-- Requires 009 (references public.organizations / public.is_org_member).
-- Additive: no existing table is modified. Both tables stay empty until the
-- backend is started with USAGE_METERING_ENABLED=true / AUDIT_TRAIL_ENABLED=true.
--
-- Neither table stores PHI: only ids, event names, counts, hashed IPs and
-- small allow-listed metadata (route, status, flags). They are deliberately
-- NOT part of the 30-day privacy purge (007) — usage is billing history and
-- audit rows are the compliance record.

create extension if not exists pgcrypto;

-- ── usage_events: one row per billable action ─────────────────────────

create table if not exists public.usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  org_id uuid references public.organizations(id) on delete set null,
  event_type text not null,
  quantity integer not null default 1 check (quantity > 0),
  units text not null default 'count',
  resource_id text,
  route text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_usage_events_user_created on public.usage_events (user_id, created_at desc);
create index if not exists idx_usage_events_org_created on public.usage_events (org_id, created_at desc);
create index if not exists idx_usage_events_type_created on public.usage_events (event_type, created_at desc);

-- ── audit_events: who did what, append-only ───────────────────────────
--
-- No foreign keys on purpose: an ON DELETE action would UPDATE/DELETE audit
-- rows, which the immutability trigger below must refuse. Deleting a user or
-- organization therefore leaves its audit history intact (bare uuids).

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid,
  org_id uuid,
  actor_type text not null default 'user' check (actor_type in ('user', 'system', 'agent')),
  action text not null,
  resource_type text,
  resource_id text,
  outcome text not null default 'success',
  reason text,
  ip_hash text,
  user_agent text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_audit_events_user_created on public.audit_events (user_id, created_at desc);
create index if not exists idx_audit_events_org_created on public.audit_events (org_id, created_at desc);
create index if not exists idx_audit_events_action_created on public.audit_events (action, created_at desc);

create or replace function public.audit_events_block_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'audit_events is append-only (% refused)', tg_op;
end;
$$;

drop trigger if exists audit_events_immutable on public.audit_events;
create trigger audit_events_immutable
  before update or delete on public.audit_events
  for each row execute function public.audit_events_block_mutation();

-- ── Row Level Security ───────────────────────────────────────────────
-- The backend writes with the service role. Users may read their own rows and
-- rows of workspaces they belong to; nobody but the service role may write.

alter table public.usage_events enable row level security;
alter table public.audit_events enable row level security;

drop policy if exists "Users can read their usage" on public.usage_events;
create policy "Users can read their usage"
  on public.usage_events for select
  using (auth.uid() = user_id or (org_id is not null and public.is_org_member(org_id)));

drop policy if exists "Users can read their audit trail" on public.audit_events;
create policy "Users can read their audit trail"
  on public.audit_events for select
  using (auth.uid() = user_id or (org_id is not null and public.is_org_member(org_id)));

grant all on table public.usage_events to service_role;
grant all on table public.audit_events to service_role;
grant select on table public.usage_events to authenticated;
grant select on table public.audit_events to authenticated;
