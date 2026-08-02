# 🚀 Deploying PolicyCrab

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
4. **Authentication:**
   - Enable Email/Password authentication in the Supabase Auth Settings.
   - Disable "Confirm Email" if you want users to be able to sign up and immediately use the app during your initial launch.

## 2. Backend Deployment (Render / AWS / Heroku)

The backend is a standard Python FastAPI application. We recommend [Render](https://render.com) for easy deployment.

1. Create a new **Web Service** on Render and connect it to your GitHub repository.
2. Set the following settings:
   - **Root Directory:** `backend`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add the following **Environment Variables** (from your `.env` file):
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `DATABASE_URL` (Use the Transaction pooler URL from Supabase)
   - `GEMINI_API_KEY`
   - `GROQ_API_KEY` / `CEREBRAS_API_KEY` (Optional for LLM routing)
   - `REDIS_URL` (If you want background async tasks to use Redis)
4. Deploy the service and note the live backend URL (e.g., `https://policycrab-api.onrender.com`).

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
4. Update `frontend/vercel.json` if needed to proxy API calls correctly to your Render backend URL.
5. Deploy the frontend.

## 4. Final Verification

1. Visit your live Vercel URL.
2. Create a test account.
3. Upload a sample policy to verify the backend is correctly processing PDFs, communicating with the LLM API, and storing data in Supabase.

---
**Need Help?**
If you have any questions during handoff, refer to the source code comments which heavily document the LangGraph agents and FastAPI routes.
