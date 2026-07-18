-- ============================================================
-- Migration 002: User Policy Vector Table
-- ============================================================
-- This table stores chunked, page-aware text from user-uploaded
-- policy PDF documents. Each chunk is embedded and indexed
-- so the Policy Analyzer Agent can perform targeted semantic
-- search against the patient's SPECIFIC policy document.
--
-- Unlike the 'knowledge_chunks' table (which stores static
-- federal/state regulatory law), this table is session-scoped —
-- each row belongs to a specific analysis session or user.
--
-- HOW TO RUN THIS:
-- 1. Go to your Supabase project → SQL Editor
-- 2. Paste this entire script and click "Run"
-- ============================================================

-- Ensure the pgvector extension is enabled (likely already from migration 001)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Table: policy_chunks ─────────────────────────────────────────
-- Stores individual text chunks from a user's uploaded policy PDF.
CREATE TABLE IF NOT EXISTS policy_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT NOT NULL,              -- Ties this chunk to a specific analysis session
    page_number     INTEGER NOT NULL,           -- Page number in the original PDF (1-indexed)
    chunk_index     INTEGER NOT NULL,           -- Index of the chunk within the page (for ordering)
    chunk_text      TEXT NOT NULL,              -- The raw text content of this chunk
    carrier_name    TEXT,                       -- Denormalized for filtering (e.g., "BlueCross")
    plan_name       TEXT,                       -- Denormalized for filtering
    embedding       VECTOR(768),                -- Gemini text-embedding-004 (768-dimensional)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (session_id, page_number, chunk_index) -- Required for upserting
);

-- ── Indexes ──────────────────────────────────────────────────────
-- Session-scoped index for fast filtering before vector similarity search
CREATE INDEX IF NOT EXISTS idx_policy_chunks_session_id
    ON policy_chunks(session_id);

-- IVFFlat index for approximate nearest-neighbor search on the embedding column.
-- 'lists' value of 100 is appropriate for up to ~1M rows. Adjust for scale.
CREATE INDEX IF NOT EXISTS idx_policy_chunks_embedding
    ON policy_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── RPC Function: search_policy_document ─────────────────────────
-- Performs cosine similarity search scoped to a single session_id.
-- This is the function the Policy Analyzer Agent calls via Supabase RPC.
--
-- Parameters:
--   p_session_id:     The session to search within (required)
--   query_embedding:  The 768-dim query vector
--   match_count:      Max number of results to return
--   similarity_threshold: Minimum cosine similarity (0.0 to 1.0)
--
-- Returns:
--   Ranked rows with id, page_number, chunk_text, and similarity score
CREATE OR REPLACE FUNCTION search_policy_document(
    p_session_id        TEXT,
    query_embedding     VECTOR(768),
    match_count         INT DEFAULT 6,
    similarity_threshold FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id          UUID,
    page_number INTEGER,
    chunk_index INTEGER,
    chunk_text  TEXT,
    similarity  FLOAT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        pc.id,
        pc.page_number,
        pc.chunk_index,
        pc.chunk_text,
        1 - (pc.embedding <=> query_embedding) AS similarity
    FROM
        policy_chunks pc
    WHERE
        pc.session_id = p_session_id
        AND 1 - (pc.embedding <=> query_embedding) > similarity_threshold
    ORDER BY
        pc.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ── Cleanup function (optional) ───────────────────────────────────
-- Deletes all chunks for a given session (call after analysis is complete
-- if you want to avoid accumulation of data).
CREATE OR REPLACE FUNCTION delete_policy_session(p_session_id TEXT)
RETURNS void
LANGUAGE sql
AS $$
    DELETE FROM policy_chunks WHERE session_id = p_session_id;
$$;

-- ── Row Level Security (RLS) ──────────────────────────────────────
-- Enable RLS to ensure sessions can only access their own chunks.
-- NOTE: For a service-key backend (which PolicyCrab uses), this is advisory.
-- The actual session_id scoping is enforced at the application layer.
ALTER TABLE policy_chunks ENABLE ROW LEVEL SECURITY;

-- ── Explicit grants for PostgREST (service role) ─────────────────
-- CRITICAL: Supabase's PostgREST uses the `service_role` database role.
-- Even though the service_role key bypasses RLS, PostgREST still needs
-- explicit GRANT on the table and functions to access them via the REST API.
GRANT ALL ON TABLE policy_chunks TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON FUNCTION search_policy_document(TEXT, VECTOR(768), INT, FLOAT) TO service_role;
GRANT EXECUTE ON FUNCTION delete_policy_session(TEXT) TO service_role;

-- Also grant to anon/authenticated for potential future direct-client access
GRANT SELECT ON TABLE policy_chunks TO authenticated;

-- ── Verification ─────────────────────────────────────────────────
-- After running, verify with:
--   SELECT COUNT(*) FROM policy_chunks;  -- should be 0 (empty table)
--   SELECT routine_name FROM information_schema.routines
--     WHERE routine_name IN ('search_policy_document', 'delete_policy_session');
--   SELECT grantee, privilege_type FROM information_schema.role_table_grants
--     WHERE table_name = 'policy_chunks';
