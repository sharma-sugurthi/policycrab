---
name: PolicyCrab deployment quirks
description: Environment-specific lessons learned while getting PolicyCrab running on a fresh Supabase project + Gemini API credentials.
---

# Deployment quirks (learned during 2026-07-26 setup)

These are durable lessons — they bite every fresh deploy until the migration set catches up.

## 1. asyncpg + Supabase pgbouncer pooler

The `DATABASE_URL` from Supabase goes through pgbouncer in `transaction` pooling mode. asyncpg uses prepared statements by default, which pgbouncer rejects.

**Symptom:** `asyncpg.exceptions.DuplicatePreparedStatementError: prepared statement "__asyncpg_stmt_1__" already exists`

**Fix:** `asyncpg.connect(dsn, statement_cache_size=0)`. Kills the prepared-statement cache; queries still work.

**How to apply:** Every provisioning/migration script that connects via `DATABASE_URL`.

## 2. PostgREST schema-cache invalidation

ALTER TABLE changes are invisible to PostgREST until it reloads its schema cache.

**Symptom:** `PGRST204 Could not find the 'X' column of 'Y' in the schema cache`

**Fix:** After applying any migration, issue `NOTIFY pgrst, 'reload schema';`

**How to apply:** Tail of every schema-migration script that runs against a live Supabase project. `provision_schema.py` does this automatically.

## 3. Service-role GRANTs required even with RLS bypass

PostgREST still needs explicit table-level GRANTs for `service_role` even though it bypasses RLS.

**Symptom:** `postgrest.exceptions.APIError: permission denied for table X (code 42501)`

**Fix:** `GRANT ALL ON TABLE public.X TO service_role;` for every user-data table.

**Why:** Migration `001_create_knowledge_base.sql` grants for `knowledge_chunks`/`policy_chunks`; older `003_create_user_chats.sql` was missing grants for `user_chats`. Fixed in current migration files. `provision_schema.py` also issues these idempotently.

## 4. BENCHMARK_TOKEN + Supabase `user_id` (uuid) column

**Symptom:** `invalid input syntax for type uuid: "benchmark_user" (code 22P02)`

**Fix:** `BENCHMARK_USER_ID = "00000000-0000-4000-8000-000000000001"` (a valid UUID-shaped string) in `backend/app/api/auth.py`. Tests that assert the bypass ID must reference `auth.BENCHMARK_USER_ID`, not a literal string.

**Why:** Supabase tables type `user_id` as uuid; the old bypass emitted a plain string.

## 5. user_id column type mismatch (varchar → uuid migration)

Older live databases created tables with `user_id text/varchar`. Migration files now declare `uuid`, but if the table pre-existed as text the migration's `CREATE TABLE IF NOT EXISTS` is a no-op and the column stays as text. RLS policies then fail with `operator does not exist: uuid = character varying`.

**Fix:**
```sql
DELETE FROM public.user_policies WHERE user_id !~ '^[0-9a-fA-F]{8}-...-[0-9a-fA-F]{12}$';
ALTER TABLE public.user_policies ALTER COLUMN user_id TYPE uuid USING user_id::uuid;
-- then recreate RLS policies
```

`provision_schema.py` now handles this automatically — it checks the column type, deletes non-UUID rows, casts, and recreates RLS.

## 6. Gemini free-tier rate limits

The free-tier GEMINI_API_KEY is capped at **20 requests/day** per model. Once exhausted, Gemini returns 429 (which the LLM router surfaces as `LLMRateLimitError` → HTTP 503). Groq has a **100k tokens/day** limit on its free tier. Both reset ~24h after the cap was hit.

**Fix in code:** `LLMRateLimitError` in `llm_router.py` is caught by route handlers and returned as HTTP 503 with `Retry-After: 120`. Routes no longer swallow rate-limit exhaustion as generic 500.

**For production:** Upgrade both API keys to paid tiers. No code changes needed.

## 7. draft-appeal request schema

`POST /api/claim/draft-appeal` expects `DraftAppealRequest`:
```json
{
  "level": 2,
  "policy_profile": { ...PolicyProfile dict... },
  "claim_case": { "cpt_code": "27447", "billed_amount": 45000.0, "network_status": "IN_NETWORK", ... },
  "level1_denial_summary": "optional string"
}
```
NOT the old `claim_description` / `appeal_level` / `route_decision` shape. The smoke script `/tmp/full_smoke.py` has been corrected.
