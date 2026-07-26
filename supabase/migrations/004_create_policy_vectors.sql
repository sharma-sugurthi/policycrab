-- Policy-specific vector storage used by policy upload and claim analysis.
-- Kept in the normal migration directory so a fresh Supabase project has the
-- same objects that the backend calls through PostgREST.

create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists public.policy_chunks (
  id uuid primary key default gen_random_uuid(),
  session_id text not null,
  page_number integer not null,
  chunk_index integer not null,
  chunk_text text not null,
  carrier_name text,
  plan_name text,
  embedding vector(768),
  created_at timestamptz not null default now(),
  unique (session_id, page_number, chunk_index)
);

create index if not exists idx_policy_chunks_session_id
  on public.policy_chunks (session_id);

create index if not exists idx_policy_chunks_embedding
  on public.policy_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create or replace function public.search_policy_document(
  p_session_id text,
  query_embedding vector(768),
  match_count int default 6,
  similarity_threshold float default 0.3
)
returns table (
  id uuid,
  page_number integer,
  chunk_index integer,
  chunk_text text,
  similarity float
)
language sql stable
as $$
  select
    pc.id,
    pc.page_number,
    pc.chunk_index,
    pc.chunk_text,
    1 - (pc.embedding <=> query_embedding) as similarity
  from public.policy_chunks pc
  where pc.session_id = p_session_id
    and pc.embedding is not null
    and 1 - (pc.embedding <=> query_embedding) > similarity_threshold
  order by pc.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.delete_policy_session(p_session_id text)
returns void
language sql
as $$
  delete from public.policy_chunks where session_id = p_session_id;
$$;

alter table public.policy_chunks enable row level security;

grant all on table public.policy_chunks to service_role;
grant execute on function public.search_policy_document(text, vector(768), int, float)
  to service_role;
grant execute on function public.delete_policy_session(text)
  to service_role;