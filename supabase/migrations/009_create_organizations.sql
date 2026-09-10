-- PolicyCrab organizations (team workspaces), memberships and email invitations.
--
-- Additive migration: existing tables only gain a NULLABLE org_id column.
-- Nothing changes for existing users until the backend is started with
-- ORGS_ENABLED=true. Safe to apply before or after deploying that backend.
--
-- Access model: the backend talks to Postgres with the service role and enforces
-- membership + role checks in app/services/organizations.py. RLS below is
-- defence-in-depth for any direct PostgREST access with a user JWT:
--   - members may READ their organizations and fellow members
--   - nobody but the service role may WRITE, and invitations (which hold token
--     hashes) are service-role only.

create extension if not exists pgcrypto;

-- ── Tables ────────────────────────────────────────────────────────────

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 80),
  slug text not null unique,
  owner_id uuid not null references auth.users(id) on delete cascade,
  plan text not null default 'team',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.org_members (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  -- Denormalised from the JWT at join time: auth.users is not readable via
  -- PostgREST, and the members table must show who is who.
  email text,
  role text not null check (role in ('owner', 'admin', 'member', 'viewer')),
  invited_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (org_id, user_id)
);

create index if not exists idx_org_members_user on public.org_members (user_id);
create index if not exists idx_org_members_org on public.org_members (org_id);

create table if not exists public.org_invitations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations(id) on delete cascade,
  email text not null,
  role text not null check (role in ('admin', 'member', 'viewer')),
  -- SHA-256 of the one-time token. The raw token exists only in the email.
  token_hash text not null unique,
  invited_by uuid references auth.users(id) on delete set null,
  expires_at timestamptz not null,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_org_invitations_org on public.org_invitations (org_id);
create index if not exists idx_org_invitations_email on public.org_invitations (lower(email));

-- ── Workspace scoping of existing data (nullable, no backfill) ────────

alter table public.user_claims
  add column if not exists org_id uuid references public.organizations(id) on delete set null;
alter table public.user_policies
  add column if not exists org_id uuid references public.organizations(id) on delete set null;

create index if not exists idx_user_claims_org on public.user_claims (org_id, created_at desc);
create index if not exists idx_user_policies_org on public.user_policies (org_id, created_at desc);

-- appeal_outcomes.org_id (migration 008) stays a bare uuid: adding a foreign
-- key would fail if any row already carries a value, and the column is unused.

-- ── Row Level Security ───────────────────────────────────────────────

-- A policy on org_members that queries org_members would recurse. This
-- SECURITY DEFINER helper performs the membership lookup outside RLS.
create or replace function public.is_org_member(target_org uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1 from public.org_members
    where org_id = target_org and user_id = auth.uid()
  );
$$;

revoke all on function public.is_org_member(uuid) from public;
grant execute on function public.is_org_member(uuid) to authenticated, service_role;

alter table public.organizations enable row level security;
alter table public.org_members enable row level security;
alter table public.org_invitations enable row level security;

drop policy if exists "Members can read their organizations" on public.organizations;
create policy "Members can read their organizations"
  on public.organizations for select
  using (public.is_org_member(id));

drop policy if exists "Members can read fellow members" on public.org_members;
create policy "Members can read fellow members"
  on public.org_members for select
  using (public.is_org_member(org_id));

-- No policies on org_invitations: readable/writable by the service role only.

-- ── Grants ───────────────────────────────────────────────────────────

grant all on table public.organizations to service_role;
grant all on table public.org_members to service_role;
grant all on table public.org_invitations to service_role;
grant select on table public.organizations to authenticated;
grant select on table public.org_members to authenticated;
