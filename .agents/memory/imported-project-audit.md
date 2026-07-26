---
name: Imported project audit
description: Durable setup risks found while auditing the imported PolicyCrab application.
---

The policy-specific vector store is defined in a separate backend SQL script rather than the numbered Supabase migration set, so a fresh environment can appear partially healthy while policy RAG is unavailable.

**Why:** The application calls `policy_chunks` and its RPC during ingestion/search, but the primary migration directory only creates the regulatory knowledge base and user history tables.

**How to apply:** Any Replit setup or deployment plan must explicitly provision the policy vector table/RPC and verify both RAG stores before declaring the application runnable.