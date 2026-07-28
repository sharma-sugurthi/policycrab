-- PolicyCrab Document Vault & Bill Auditor persistent storage tables.
-- Follows established security patterns from user_policies and user_claims tables.

create extension if not exists pgcrypto;

-- ── Table: user_documents ─────────────────────────────────────────
create table if not exists public.user_documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  document_type text not null default 'unknown',
  extraction_method text,
  extracted_json jsonb not null,
  is_denied boolean default false,
  billed_amount numeric,
  created_at timestamptz not null default now()
);

create index if not exists idx_user_documents_user_created
  on public.user_documents (user_id, created_at desc);

-- ── Table: user_audits ─────────────────────────────────────────────
create table if not exists public.user_audits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  service_lines_json jsonb not null,
  audit_result_json jsonb not null,
  dispute_letter text,
  overall_risk text not null default 'low',
  total_billed numeric default 0.0,
  potential_savings numeric,
  source text not null default 'manual',
  created_at timestamptz not null default now()
);

create index if not exists idx_user_audits_user_created
  on public.user_audits (user_id, created_at desc);

-- ── Row Level Security (RLS) ───────────────────────────────────────
alter table public.user_documents enable row level security;
alter table public.user_audits enable row level security;

-- user_documents policies
drop policy if exists "Users can read their documents" on public.user_documents;
create policy "Users can read their documents"
  on public.user_documents for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their documents" on public.user_documents;
create policy "Users can insert their documents"
  on public.user_documents for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete their documents" on public.user_documents;
create policy "Users can delete their documents"
  on public.user_documents for delete
  using (auth.uid() = user_id);

-- user_audits policies
drop policy if exists "Users can read their audits" on public.user_audits;
create policy "Users can read their audits"
  on public.user_audits for select
  using (auth.uid() = user_id);

drop policy if exists "Users can insert their audits" on public.user_audits;
create policy "Users can insert their audits"
  on public.user_audits for insert
  with check (auth.uid() = user_id);

drop policy if exists "Users can update their audits" on public.user_audits;
create policy "Users can update their audits"
  on public.user_audits for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "Users can delete their audits" on public.user_audits;
create policy "Users can delete their audits"
  on public.user_audits for delete
  using (auth.uid() = user_id);

-- ── Service-role grants ─────────────────────────────────────────────
GRANT ALL ON TABLE public.user_documents TO service_role;
GRANT ALL ON TABLE public.user_audits    TO service_role;
