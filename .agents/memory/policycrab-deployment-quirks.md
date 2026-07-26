---
name: PolicyCrab deployment quirks
description: Environment-specific lessons learned while getting PolicyCrab running on a fresh Supabase project + Gemini API credentials.
---

# Deployment quirks (learned during 2026-07-26 setup)

These are durable lessons — they bite every fresh deploy until the migration set catches up. Code in the repo currently assumes them; surface issues only surface when you provision a brand-new Supabase project.

## 1. asyncpg + Supabase pgbouncer pooler

The `DATABASE_URL` that Supabase hands out goes through pgbouncer in `transaction` pooling mode. asyncpg uses prepared statements by default, which pgbouncer refuses. Symptom:

```
asyncpg.exceptions.DuplicatePreparedStatementError: prepared statement "__asyncpg_stmt_1__" already exists
```

**Fix:** pass `statement_cache_size=0` to `asyncpg.connect(dsn, statement_cache_size=0)`. This kills prepared-statement caching; queries still work, just without the perf optimization.

**Why:** Supabase docs recommend asyncpg's own pooling over pgbouncer for prepared statements. When you have to use pgbouncer, the cache-size toggle is the documented workaround.

**How to apply:** Any provisioning / migration script that connects via `DATABASE_URL` (see `backend/scripts/provision_schema.py`, `full_smoke.py`). Don't undo this without first verifying the URL no longer routes through pgbouncer.

## 2. PostgREST schema-cache invalidation

`ALTER TABLE` via Supabase's pooler goes through, but PostgREST caches the OpenAPI schema it generates from `information_schema`. New columns appear "missing" with `PGRST204` until PostgREST reloads. Symptom:

```
postgrest.exceptions.APIError: Could not find the 'X' column of 'Y' in the schema cache
```

**Fix:** after applying migrations, send `NOTIFY pgrst, 'reload schema';` (or `NOTIFY pgrst, 'reload config';` on the config side). This rebroadcasts the schema delta to PostgREST.

**Why:** PostgREST is schema-driven; it polls once on startup. Adding columns mid-session without a notify is silently invisible until restart.

**How to apply:** Add the notify at the tail of every schema-migration script that runs against a live Supabase project (the provision script does this — see `provision_schema.py`).

## 3. Service-role GRANTs required even with RLS bypass

RLS bypass applies only to roles that PostgREST treats as "privileged". `service_role` (the role the Python supabase client uses when you pass the service-key JWT) is privileged, but PostgREST still requires explicit GRANTs on the table itself. Symptom:

```
postgrest.exceptions.APIError: permission denied for table X (code 42501)
```

**Fix:** `GRANT ALL ON TABLE public.X TO service_role;` for every user-data table (`user_policies`, `user_claims`, `user_chats`).

**Why:** PostgREST enforces grants at the API layer independent of RLS. Migration `001_create_knowledge_base.sql` grants for `knowledge_chunks` and `policy_chunks`; `003_create_user_chats.sql` does NOT — it only sets up `authenticated`-role policies. The gap shows up as 500s on chat/history routes.

**How to apply:** Any fresh Supabase project needs the supplemental grant pass from the provision script. Consider backporting these into the published migration files so the next deploy doesn't hit the same 42501.

## 4. BENCHMARK_TOKEN + Supabase `user_id` (uuid) column

`verify_supabase_token()` returns `{"id": "benchmark_user"}` for the `BENCHMARK_TOKEN` bypass. Supabase tables type `user_id` as `uuid`. Inserting the string `"benchmark_user"` fails with:

```
postgrest.exceptions.APIError: invalid input syntax for type uuid: "benchmark_user" (code 22P02)
```

**Fix:** set `BENCHMARK_USER_ID = "00000000-0000-4000-8000-000000000001"` (a valid UUIDv4-shaped string) and use it as the `id` in the bypass branch. The fix is in `backend/app/api/auth.py`.

**Why:** Real Supabase users have UUID `sub` claims, so the tables must be typed UUID. The benchmark bypass path was originally for in-memory unit tests where the table type didn't matter.

**How to apply:** When wiring any future bypass, dev-login, or migration-script that pretends to be a user, always emit a valid UUID for `id`.

## 5. Legacy RLS policy type mismatch with `auth.uid()`

If `user_policies.user_id` was created as `text` (older migration) and a later migration tries to create RLS policies using `auth.uid() = user_id`, Postgres aborts the policy with:

```
operator does not exist: uuid = character varying
```

The error aborts the WHOLE migration transaction, so any `ADD COLUMN` statements in the same file silently fail too.

**Fix:** ensure each table's `user_id` is `uuid` before adding RLS, or sequence migrations so `ALTER COLUMN ... TYPE uuid` runs first.

**Why:** Older setups provisioned with the original `text` typed columns; current migrations assume `uuid`.

**How to apply:** Manual recovery: `ALTER TABLE public.user_policies ALTER COLUMN user_id TYPE uuid USING user_id::uuid;` plus recreate FK + policies. Don't ship migrations that mix column-type assumptions.
