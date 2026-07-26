---
name: PolicyCrab operating notes
description: Day-to-day notes for running PolicyCrab on Replit — workflows, smoke drive, and where state lives.
---

# Operating PolicyCrab on Replit

## Secrets required (Replit Secrets, never .env)

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `GEMINI_API_KEY`, `DATABASE_URL` are mandatory.
Optional: `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`.

## Workflows

Two workflows, both must run:

- `PolicyCrab Backend` — `cd backend && DEBUG=true uvicorn app.main:app --host 0.0.0.0 --port 8000`. (`DEBUG=true` enables `BENCHMARK_TOKEN` auth bypass for smoke tests. Set `false` in real-user deploys.)
- `PolicyCrab Frontend` — `cd frontend && npm run dev -- --host 0.0.0.0` on port 5000 (vite). Vite proxies `/api/*` → `http://localhost:8000`.

## End-to-end smoke drive

After every fresh deploy (or DB reset):

```bash
python /home/runner/workspace/backend/scripts/provision_schema.py   # idempotent
python /home/runner/workspace/backend/scripts/full_smoke.py         # upload → evaluate → chat
python /tmp/full_smoke.py                                            # 12-endpoint coverage
```

`full_smoke.py` uses `BENCHMARK_TOKEN` so it doesn't require an actual Supabase user. It exercises Gemini Flash + Pro, the deterministic cost engine, RAG appeal drafting, and Supabase persistence.

## Where state lives

- App state (policy profile in progress): Vite localStorage / sessionStorage (see `App.jsx` SS_POLICY_KEY, LS_*_KEY). Wiped on browser restart for the LOCAL profile persistence.
- User history: Supabase `user_policies`, `user_claims`, `user_chats` rows keyed by Supabase `auth.users.id`. RLS via `authenticated` role; backend uses `service_role` (with the explicit GRANTs).
- Regulatory RAG: `knowledge_chunks` (46 chunks preloaded; concept_id / domain / jurisdiction / semantic_summary).
- Per-policy-doc RAG: `policy_chunks` (IVFFlat over 768-d Gemini embeddings; session_id-scoped).

## Pitfalls (covered with fixes)

See `policycrab-deployment-quirks.md` for the asyncpg / PostgREST / GRANTs / benchmark-UUID story.
