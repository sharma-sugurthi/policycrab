# PolicyCrab API Backend

This is the FastAPI backend for the PolicyCrab platform. It provides the core adjudication engine, RAG policy ingestion, and AI appeal drafting services.

## Architecture

- **FastAPI**: High-performance async web framework.
- **Supabase**: PostgreSQL database (with `pgvector` for RAG) and Authentication.
- **LangGraph & LangChain**: Orchestrates the multi-agent appeal and evaluation workflow.
- **PyMuPDF**: Parses uploaded SBC and EOB documents.

## Local Setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your environment variables in the root `.env` file (see `../.env.example`).
4. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Testing

To run the unit and integration tests:
```bash
pip install -r requirements-dev.txt
pytest tests/
```
