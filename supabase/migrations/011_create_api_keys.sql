-- PolicyCrab API keys: programmatic access for integrations (RCM systems,
-- advocacy case-management tools). Requires 009 (organizations).
--
-- A key is created by a signed-in user, either for themselves (org_id NULL)
-- or for a workspace they administer. Only the SHA-256 of the key is stored;
-- the key itself is shown once at creation. Every key carries an explicit
-- scope list; the backend maps each route to the scope it needs and refuses
-- anything unlisted (workspace/admin/key management are never key-callable).
--
-- Inert until the backend runs with API_KEYS_ENABLED=true.

create extension if not exists pgcrypto;

create table if not exists public.api_keys (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,        -- owner: requests run as this user
  owner_email text,                                                          -- denormalised for display
  org_id uuid references public.organizations(id) on delete cascade,        -- NULL = personal key
  name text not null check (char_length(name) between 1 and 80),
  key_prefix text not null,                                                  -- first 16 chars, display only
  key_hash text not null unique,                                             -- sha256(full key)
  scopes text[] not null default '{}',
  environment text not null default 'live' check (environment in ('live', 'test')),
  last_used_at timestamptz,
  expires_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_api_keys_user on public.api_keys (user_id);
create index if not exists idx_api_keys_org on public.api_keys (org_id);

alter table public.api_keys enable row level security;

drop policy if exists "Users can read their api keys" on public.api_keys;
create policy "Users can read their api keys"
  on public.api_keys for select
  using (auth.uid() = user_id or (org_id is not null and public.is_org_member(org_id)));

-- Writes go through the backend (service role) only.
grant all on table public.api_keys to service_role;
grant select on table public.api_keys to authenticated;
