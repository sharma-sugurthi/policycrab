# PolicyCrab: AI-Powered US Healthcare Advocacy Engine

**PolicyCrab** is a fully functional, production-ready AI platform designed to help Americans navigate the complexities of their healthcare insurance. It automatically ingests complex policy documents (SBCs/EOBs), deterministically evaluates claims for over-billing or regulatory violations, and uses autonomous agents to generate legally sound appeal letters.

This is a premium SaaS codebase built on a modern AI stack, perfect for an entrepreneur or organization looking to enter the $4 Trillion US healthcare market with a powerful, automated advocacy tool.

---

## 🚀 The Opportunity

The US healthcare billing system is notoriously opaque, with up to **80% of medical bills containing errors**, and millions of claims being wrongfully denied each year. PolicyCrab automates the job of a professional medical bill advocate.

**Core Value Proposition:**
- **For Consumers:** Save thousands of dollars by identifying billing errors and successfully appealing denied claims.
- **For B2B/HR:** Offer as a premium benefit to employees to reduce their out-of-pocket healthcare expenses.
- **For the Acquirer:** A turnkey, highly scalable AI platform with immediate monetization potential (e.g., $15-$50 per generated appeal letter, or a $10/mo subscription).

## 🛠 Tech Stack

PolicyCrab uses a cutting-edge, highly deterministic architecture to ensure medical math is accurate (preventing LLM hallucination) while leveraging AI for complex reasoning and writing.

- **Frontend:** React, Vite, Framer Motion, Vanilla CSS (Premium, custom-branded UI).
- **Backend:** FastAPI (Python), SQLAlchemy, asyncpg.
- **AI Agents & RAG:** LangGraph, LangChain. Uses a curated, localized knowledge base covering federal regulations (ERISA, ACA, NSA, Medicare, HIPAA).
- **LLM Routing:** Intelligent Multi-LLM setup. Groq (Llama 3) for fast, cheap data extraction; Google Gemini 2.5 Pro for complex reasoning and drafting.
- **Document Processing:** PyMuPDF, Pytesseract (OCR for scanned images).
- **Database & Auth:** Supabase (PostgreSQL pgvector for embeddings, Auth JWTs for user sessions).

## ✨ Key Features

1. **AI Policy Ingestion (RAG):** Extracts complex SBC/EOB terms into a normalized deterministic schema. Includes OCR fallback for scanned images.
2. **Deterministic Adjudication Engine:** Accurately calculates patient responsibilities (deductibles, coinsurance, OOP maximums, NSA protections) with exact math, bypassing LLM limitations on numerical reasoning.
3. **Automated ERISA Appeals (Interactive Studio):** If a claim is denied, the engine triggers an autonomous agent to draft a formal, legally grounded appeal letter using federal guidelines. Users can review, tweak, and generate a final PDF dossier.
4. **Interactive AI Advocate:** A contextual chat assistant that references the user's specific policy and claim to answer regulatory questions.
5. **Secure Dashboard & History:** Powered by Supabase, users can save and revisit past policies, track claim evaluations, and monitor statutory deadlines.
6. **Bill Auditor:** Analyzes itemized medical bills line-by-line for upcoding or unbundling errors.

## 📂 Repository Structure

```
├── frontend/               # React + Vite user interface
├── backend/                # FastAPI Python application
│   ├── app/
│   │   ├── agents/         # LangGraph AI agents (appeal, ingestion, triage)
│   │   ├── engine/         # Deterministic calculators (costs, deadlines)
│   │   ├── api/            # API routing and endpoints
│   │   └── models/         # Pydantic data schemas
│   └── tests/              # Pytest suite and synthetic benchmarks
├── supabase/
│   └── migrations/         # PostgreSQL schema and RLS policies
├── knowledge_base/         # Curated US healthcare regulation markdown files
├── .env.example            # Environment variables template
├── DEPLOYMENT.md           # Instructions for deploying to production
├── CHANGELOG.md            # Version history and feature list
└── SECURITY.md             # Security and PHI handling policies
```

## ⚡ Getting Started (Local Development)

### 1. Clone & Install

```bash
# Clone the repository
git clone <repository_url>
cd policycrab

# Backend Setup
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend Setup
cd ../frontend
npm install
```

### 2. Configure Environment

Copy `.env.example` to `.env` in the root directory. You will need API keys for:
- Supabase (URL, Anon Key, Service Role Key)
- Google Gemini API
- Groq / Cerebras / OpenRouter (Optional, for optimized routing)

### 3. Run the Application

```bash
# Terminal 1 — Start the Backend Server
cd backend
uvicorn app.main:app --reload

# Terminal 2 — Start the Frontend App
cd frontend
npm run dev
```

Visit: `http://localhost:5000`

## 🤝 Support & Documentation

The codebase is clean, well-commented, and heavily modularized. See the following documents for more details:
- [DEPLOYMENT.md](DEPLOYMENT.md) - For deploying to production (Vercel/Render).
- [SECURITY.md](SECURITY.md) - For data privacy and infrastructure protection.
- [CHANGELOG.md](CHANGELOG.md) - To review all current platform features.

---
*Built for the future of patient advocacy.*
