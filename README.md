# 🦀 PolicyCrab

**AI-powered US health insurance claims engine.**

Upload your policy → Evaluate your claim → Get a regulatory-backed appeal letter.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite, Framer Motion, Vanilla CSS (PolicyCrab branded) |
| Backend | FastAPI, LangGraph, LangChain, PyMuPDF, Pytesseract, SQLAlchemy, asyncpg |
| Database & Auth | Supabase (PostgreSQL pgvector, Auth JWT) |
| LLM Providers | Google Gemini, Groq, Cerebras |
| RAG | 46-chunk knowledge base (ERISA, ACA, NSA, Medicare, HIPAA) |

## Key Features

1. **AI Policy Ingestion (RAG):** Extracts complex SBC/EOB terms into a normalized deterministic schema. Includes OCR fallback for scanned images.
2. **Deterministic Adjudication Engine:** Accurately calculates patient responsibilities (deductibles, coinsurance, OOP maximums, NSA protections) with exact math, preventing LLM hallucination on numbers.
3. **Automated ERISA Appeals:** If a claim is denied, the engine triggers an autonomous agent to draft a formal, legally grounded appeal letter using federal guidelines.
4. **Interactive AI Advocate:** A chat assistant that references the user's specific policy and claim to answer regulatory questions.
5. **Multi-LLM Routing:** Intelligently routes basic extraction to fast models (Groq Llama 3) and complex reasoning/writing to high-quality models (Gemini 2.5 Pro).
6. **Secure Auth & History:** Powered by Supabase JWTs and SQLAlchemy, users can save and revisit past policies and claim evaluations.

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
