# 🦀 PolicyCrab

**AI-powered US health insurance claims engine.**

Upload your policy → Evaluate your claim → Get a regulatory-backed appeal letter.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite, Framer Motion |
| Backend | FastAPI + LangGraph |
| AI | Google Gemini (multi-LLM router) |
| Database | Supabase (PostgreSQL + pgvector) |
| Auth | Supabase Auth |
| RAG | 46-chunk knowledge base (ERISA, ACA, NSA, Medicare, HIPAA) |

## Features

- 📋 **Policy Upload** — Paste text or upload a PDF SBC/EOB
- ⚡ **Claim Evaluation** — Deterministic deductible → coinsurance → OOP max waterfall
- ⚖️ **Appeal Generation** — RAG-powered appeal letters citing federal regulations
- 💬 **AI Chat** — Domain-restricted insurance Q&A with citation tracking
- 🔒 **Auth** — Supabase email/password authentication

## Regulatory Frameworks

- ERISA (self-funded employer plans)
- ACA (marketplace & essential benefits)
- No Surprises Act (balance billing defense)
- Medicare (5-level appeal process)
- HIPAA (privacy compliance)

## Getting Started

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/policycrab.git
cd policycrab

# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Configure environment

```bash
cp .env.example .env
# Fill in your Supabase and Gemini API keys
```

### 3. Run

```bash
# Terminal 1 — Backend
uvicorn app.main:app --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Visit: http://localhost:5173

## Project Structure

```
policycrab/
├── app/
│   ├── agents/          # LangGraph agent nodes
│   ├── api/             # FastAPI route handlers
│   ├── engine/          # Deterministic cost calculator
│   ├── models/          # Pydantic data models
│   ├── services/        # Supabase, LLM router, PDF extractor
│   └── tools/           # RAG search, CPT/ICD lookup
├── frontend/
│   └── src/
│       ├── pages/       # Home, PolicyUpload, ClaimEvaluator, ChatAssistant
│       └── contexts/    # AuthContext
├── knowledge_base/      # Raw markdown regulatory documents
├── supabase/
│   └── migrations/      # Database schema
└── tests/               # Pytest unit tests (37 passing)
```

## License

MIT
