-- =============================================================================
-- Migration 003: Heading-Aware RAG — Section Heading Column
--
-- Purpose:
--   Adds a `section_heading` column to the policy_chunks table so that each
--   chunk knows which section of the policy document it belongs to
--   (e.g., EXCLUSIONS, APPEALS, DEFINITIONS).
--
--   This enables the Policy Analyzer to do two kinds of retrieval:
--     1. Semantic search  — finds contextually relevant clauses (existing)
--     2. Structural anchor — always fetches EXCLUSIONS, APPEALS, DEFINITIONS
--        regardless of semantic similarity (NEW)
--
-- Safe to run on existing data: the column is nullable with DEFAULT NULL,
-- so existing rows are unaffected and semantic search continues to work.
-- =============================================================================

-- Step 1: Add section_heading column (idempotent)
ALTER TABLE policy_chunks
  ADD COLUMN IF NOT EXISTS section_heading TEXT DEFAULT NULL;

-- Step 2: Create index for fast keyword lookups on section_heading
CREATE INDEX IF NOT EXISTS idx_policy_chunks_section_heading
  ON policy_chunks (session_id, section_heading)
  WHERE section_heading IS NOT NULL;

-- Step 3: Replace the search_policy_document RPC with an updated version
-- that supports optional keyword filtering on section_heading.
-- Existing callers passing no section_filter continue to work identically.
DROP FUNCTION IF EXISTS search_policy_document(TEXT, VECTOR, INT, FLOAT);

CREATE OR REPLACE FUNCTION search_policy_document(
  p_session_id        TEXT,
  query_embedding     VECTOR(768),
  match_count         INT     DEFAULT 6,
  similarity_threshold FLOAT  DEFAULT 0.25,
  section_filter      TEXT    DEFAULT NULL
)
RETURNS TABLE (
  page_number     INT,
  chunk_index     INT,
  chunk_text      TEXT,
  section_heading TEXT,
  similarity      FLOAT
)
LANGUAGE sql STABLE
AS $$
  SELECT
    page_number,
    chunk_index,
    chunk_text,
    section_heading,
    1 - (embedding <=> query_embedding) AS similarity
  FROM policy_chunks
  WHERE session_id = p_session_id
    -- When section_filter is provided, filter by keyword match on section_heading.
    -- When NULL, all chunks are eligible (pure semantic search mode).
    AND (
      section_filter IS NULL
      OR section_heading ILIKE '%' || section_filter || '%'
    )
    AND 1 - (embedding <=> query_embedding) >= similarity_threshold
  ORDER BY similarity DESC
  LIMIT match_count;
$$;

-- Step 4: Structural anchor function — fetch chunks from a specific policy
-- section by keyword match ONLY (no semantic similarity involved).
-- Used to guarantee EXCLUSIONS, APPEALS, DEFINITIONS are always in context.
DROP FUNCTION IF EXISTS fetch_policy_section(TEXT, TEXT, INT);

CREATE OR REPLACE FUNCTION fetch_policy_section(
  p_session_id  TEXT,
  section_type  TEXT,
  max_chunks    INT DEFAULT 4
)
RETURNS TABLE (
  page_number     INT,
  chunk_index     INT,
  chunk_text      TEXT,
  section_heading TEXT
)
LANGUAGE sql STABLE
AS $$
  SELECT page_number, chunk_index, chunk_text, section_heading
  FROM policy_chunks
  WHERE session_id = p_session_id
    AND section_heading ILIKE '%' || section_type || '%'
  ORDER BY page_number ASC, chunk_index ASC
  LIMIT max_chunks;
$$;
