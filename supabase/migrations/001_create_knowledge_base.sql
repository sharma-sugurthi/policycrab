-- ============================================
-- US Policy Claimer: Knowledge Base Schema
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create the knowledge_chunks table
CREATE TABLE knowledge_chunks (
    id BIGSERIAL PRIMARY KEY,
    concept_id TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    audience TEXT NOT NULL,
    tags TEXT[] NOT NULL,
    title TEXT NOT NULL,
    semantic_summary TEXT NOT NULL,
    full_content TEXT NOT NULL,
    embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create HNSW index for fast vector similarity search
CREATE INDEX idx_knowledge_embedding ON knowledge_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Create indexes for metadata filtering (hybrid search)
CREATE INDEX idx_knowledge_domain ON knowledge_chunks(domain);
CREATE INDEX idx_knowledge_jurisdiction ON knowledge_chunks(jurisdiction);
CREATE INDEX idx_knowledge_audience ON knowledge_chunks(audience);
CREATE INDEX idx_knowledge_tags ON knowledge_chunks USING GIN(tags);

-- 5. Create the hybrid search function
CREATE OR REPLACE FUNCTION search_knowledge(
    query_embedding VECTOR(768),
    filter_domain TEXT DEFAULT NULL,
    filter_jurisdiction TEXT DEFAULT NULL,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id BIGINT,
    concept_id TEXT,
    title TEXT,
    semantic_summary TEXT,
    full_content TEXT,
    domain TEXT,
    jurisdiction TEXT,
    tags TEXT[],
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kc.id,
        kc.concept_id,
        kc.title,
        kc.semantic_summary,
        kc.full_content,
        kc.domain,
        kc.jurisdiction,
        kc.tags,
        1 - (kc.embedding <=> query_embedding) AS similarity
    FROM knowledge_chunks kc
    WHERE
        (filter_domain IS NULL OR kc.domain = filter_domain)
        AND (filter_jurisdiction IS NULL OR kc.jurisdiction = filter_jurisdiction)
    ORDER BY kc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ── Service-role grants ──────────────────────────────────────────────
-- The Supabase PostgREST service-role user needs explicit grants to
-- SELECT from knowledge_chunks and EXECUTE the search function.
-- Without these, /api/knowledge/search returns 500 on a fresh project.
GRANT ALL ON TABLE public.knowledge_chunks TO service_role;
GRANT ALL ON SEQUENCE public.knowledge_chunks_id_seq TO service_role;
GRANT EXECUTE ON FUNCTION public.search_knowledge(
    vector(768), text, text, int
) TO service_role;
