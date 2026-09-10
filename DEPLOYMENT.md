#  Deploying PolicyCrab

This guide explains how to deploy PolicyCrab to a production environment. The application consists of a **FastAPI backend** and a **React frontend**, plus a **Supabase** project for the database and authentication.

## 1. Supabase (Database & Auth)

Supabase provides the managed PostgreSQL database (with `pgvector` for AI embeddings) and handles user authentication.

1. Create a new project on [Supabase](https://supabase.com).
2. Note your **Project URL**, **anon key**, and **service_role key**.
3. **Database Migrations:**
   - Go to the SQL Editor in your Supabase dashboard.
   - Run the SQL files found in `supabase/migrations/` in order to create the necessary tables and policies:
     1. `001_create_knowledge_base.sql`
     2. `002_create_user_data_tables.sql`
     3. `003_create_user_chats.sql`
     4. `004_create_policy_vectors.sql`
     5. `005_create_documents_and_audits.sql`
     6. `006_chat_history.sql`
     7. `007_hipaa_auto_purge.sql`
     8. `008_create_appeal_outcomes.sql` — appeal outcome tracking for success-score calibration (`/api/outcomes`). Apply **before** deploying a backend that includes the Accuracy Core; the table holds no PHI and is deliberately excluded from the 30-day purge.
     9. `009_create_organizations.sql` — team workspaces (`organizations`, `org_members`, `org_invitations`) plus a nullable `org_id` on `user_claims` and `user_policies`. Inert until `ORGS_ENABLED=true`, so it is safe to apply at any time; existing rows are untouched.
4. **Authentication:**
   - Enable Email/Password authentication in the Supabase Auth Settings.
   - Disable "Confirm Email" if you want users to be able to sign up and immediately use the app during your initial launch.

## 2. Backend Deployment (Google Cloud Run)

The backend is a standard Python FastAPI application. We use **Google Cloud Run** for serverless, scalable deployment, automated via GitHub Actions Workload Identity Federation.

1. Setup a Google Cloud Project and enable the Cloud Run API.
2. In your GitHub repository, configure the necessary repository secrets for GCP deployment (e.g., `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`).
3. Set the following **Environment Variables** in your Cloud Run service (or via GitHub Secrets depending on your setup):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `DATABASE_URL` (Use the Transaction pooler URL from Supabase)
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY` / `CEREBRAS_API_KEY` (Optional for LLM routing)
   - `REDIS_URL` (If you want background async tasks to use Redis)
   - **Accuracy Core (optional — defaults shown are the safe production values):**
     - `CITATION_UNVERIFIED_POLICY=annotate` — how statutes the LLM cited but PolicyCrab cannot verify are handled: `annotate` inserts a visible `[VERIFY: ...]` marker (original letter preserved), `strip` removes them, `off` reports only.
     - `CITATION_POLICY_FUZZY_THRESHOLD=0.85` — minimum similarity for a quoted policy clause to count as found in the retrieved policy chunks.
     - `QUALITY_GATE_MODE=warn` — `warn` drafts with bracketed placeholders and attaches a missing-information checklist; `block` refuses to draft when critical facts (denial date, billed amount, plan classification, unreconciled EOB math) are missing; `off` disables the gate.
   - After deploying, run `python scripts/build_citation_allowlist.py --checklist` from `backend/` and have a maintainer open each listed source URL to set `verified_on` in `app/engine/citation_allowlist.py`. Until then every letter carries the flag `ALLOWLIST_NEEDS_HUMAN_VERIFICATION` (visible in the UI as "reference list pending review").
   - **Team workspaces (optional — off by default):**
     - `ORGS_ENABLED=false` — set to `true` to expose `/api/orgs` and the Team Workspaces UI. Requires migration 009. With it off, the frontend hides every team control and the backend ignores the `X-Org-Id` header, so single-user behaviour is unchanged.
     - `APP_BASE_URL=https://policycrab.tech` — public frontend URL used to build invitation links (`/invite?token=...`).
     - `ORG_INVITATION_TTL_DAYS=7` — how long an invitation link stays valid.
     - Invitation emails go through the existing `RESEND_API_KEY`. When it is not set, the one-time link is returned to the inviting admin in the UI instead of being emailed.
4. The deployment is handled automatically by the GitHub Actions pipeline upon merging to the `main` branch. Note the live backend URL (e.g., `https://policycrab-api-xyz.a.run.app`).

## 3. Frontend Deployment (Vercel)

The frontend is a Vite-powered React application. We recommend [Vercel](https://vercel.com) for blazing-fast edge hosting.

1. Create a new project on Vercel and connect your GitHub repository.
2. Set the following settings:
   - **Framework Preset:** `Vite`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Add the following **Environment Variables**:
   - `VITE_SUPABASE_URL`: Your Supabase Project URL.
   - `VITE_SUPABASE_ANON_KEY`: Your Supabase anon key.
4. Update `frontend/vercel.json` if needed to proxy API calls correctly to your Cloud Run backend URL.
5. Deploy the frontend.

## 4. Final Verification

1. Visit your live Vercel URL.
2. Create a test account.
3. Upload a sample policy to verify the backend is correctly processing PDFs, communicating with the LLM API, and storing data in Supabase.

---
**Need Help?**
If you have any questions, refer to the source code comments which heavily document the LangGraph agents and FastAPI routes.
