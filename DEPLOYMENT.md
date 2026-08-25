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
