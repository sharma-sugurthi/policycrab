-- Persisted chat state for one active assistant conversation per user.

create extension if not exists pgcrypto;

create table if not exists public.user_chats (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  messages jsonb not null default '[]'::jsonb,
  policy_profile_json jsonb,
  cost_breakdown_json jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id)
);

create index if not exists idx_user_chats_user_updated
  on public.user_chats (user_id, updated_at desc);

alter table public.user_chats enable row level security;

drop policy if exists "Users can read their chat" on public.user_chats;
create policy "Users can read their chat"
  on public.user_chats for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their chat" on public.user_chats;
create policy "Users can insert their chat"
  on public.user_chats for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can update their chat" on public.user_chats;
create policy "Users can update their chat"
  on public.user_chats for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ── Service-role grant ───────────────────────────────────────────────
-- Applied live by Replit provisioner; omitted from original migration file.
-- Without this the service-role client cannot UPSERT chat history, causing
-- /api/chat/message to 500 after every AI response.
GRANT ALL ON TABLE public.user_chats TO service_role;
