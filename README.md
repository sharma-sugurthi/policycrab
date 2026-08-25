# PolicyCrab: AI-Powered US Healthcare Advocacy Engine

**PolicyCrab** is an AI platform built with production practices designed to help medical advocates, HR benefits managers, and individual Americans navigate the complexities of US healthcare insurance. It automatically ingests complex policy documents (SBCs/EOBs), deterministically evaluates claims for over-billing or regulatory violations, and uses autonomous agents to generate legally sound appeal letters.

By combining strict deterministic math with advanced Multi-LLM reasoning, PolicyCrab scales the expertise of a professional medical bill advocate.

---

## 🚀 The Platform

The US healthcare billing system is notoriously opaque, with **a large share of medical bills containing errors**, and millions of claims being wrongfully denied each year. PolicyCrab tackles this problem directly with automation and regulatory intelligence.

**Core Capabilities:**
- **For Medical Advocates & Brokers:** A force-multiplier that analyzes denials, determines provider vs. payer fault, calculates deadlines, and drafts regulatory appeals.
- **For HR & Benefits Managers:** A powerful platform to reduce out-of-pocket healthcare expenses for employees, improving benefits satisfaction.
- **For Patients:** A seamless, easy-to-use interface to fight wrongful denials without needing a law degree.

## 🛠 Tech Stack & Architecture

PolicyCrab uses a cutting-edge, highly deterministic architecture to ensure medical math is accurate (preventing LLM hallucination) while leveraging AI for complex reasoning and writing.

- **Frontend:** React, Vite, Framer Motion, Vanilla CSS (Premium, custom-branded UI).
- **Backend:** FastAPI (Python), SQLAlchemy, asyncpg. Deployed on **Google Cloud Run** via GitHub Actions.
- **AI Agents & RAG:** LangGraph, LangChain. Uses a curated, localized knowledge base covering federal regulations (ERISA, ACA, NSA, Medicare, HIPAA).
- **LLM Routing:** Intelligent Multi-LLM setup. Groq (Llama 3) for fast, cheap data extraction; Google Gemini 2.5 Pro for complex reasoning and drafting.
- **Document Processing:** PyMuPDF (digital text) and **Gemini Multimodal API** (native OCR/vision for complex tables and scanned PDFs).
- **Database & Auth:** Supabase (PostgreSQL pgvector for embeddings, Auth JWTs for user sessions).

## ✨ Key Features

1. **AI Policy Ingestion (RAG):** Extracts complex SBC/EOB terms into a normalized deterministic schema. Includes Gemini Multimodal for pixel-perfect table extraction on scanned images.
2. **Deterministic Adjudication Engine:** Accurately calculates patient responsibilities (deductibles, coinsurance, OOP maximums, NSA protections) with exact math, bypassing LLM limitations on numerical reasoning.
3. **Automated ERISA & ACA Appeals (Interactive Studio):** If a claim is denied, the engine triggers an autonomous agent to draft a formal, legally grounded appeal letter using federal guidelines. Users can review, tweak (Assertive, Simplify, Medical Urgency modifiers), and generate a final PDF dossier.
4. **Intelligent Triage & Carrier Intelligence:** Routes denials accurately between Provider Errors (upcoding, unbundling) and Payer Violations, utilizing litigation-aware appeal tactics per insurer (e.g., UHC's nH Predict, Cigna's PXDX).
5. **Interactive AI Advocate:** A contextual chat assistant with multi-thread persistent history that references the user's specific policy and claim to answer regulatory questions.
6. **Enterprise AI Security Framework (EASF):** Employs strict "Agentic Zero Trust" boundaries. Includes local heuristic Prompt Injection Shields, a Deterministic Policy Engine to govern tool calls, and complete JSON Audit Logging for all AI decisions.
7. **Privacy-First HIPAA Compliance:** Uses local scrubbing tools (Microsoft Presidio) before data leaves the server, and utilizes Supabase `pg_cron` to automatically delete raw, sensitive EOB extractions after 30 days.

## 📂 Repository Structure

```text
├── frontend/               # React + Vite user interface
├── backend/                # FastAPI Python application
│   ├── app/
│   │   ├── agents/         # LangGraph AI agents (appeal, ingestion, triage)
│   │   ├── engine/         # Deterministic calculators (costs, deadlines)
│   │   ├── security/       # Enterprise AI Security Framework (EASF)
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
- Groq / Cerebras (Optional, for optimized routing)

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
- [DEPLOYMENT.md](DEPLOYMENT.md) - For deploying to production (Vercel & Google Cloud Run).
- [SECURITY.md](SECURITY.md) - For data privacy and infrastructure protection.
- [CHANGELOG.md](CHANGELOG.md) - To review all current platform features.

---
*PolicyCrab: The Future of Patient Advocacy.*
