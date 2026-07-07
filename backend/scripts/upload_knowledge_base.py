"""
US Policy Claimer — Knowledge Base Embedding & Upload Pipeline
Parses all knowledge base markdown files, generates embeddings via
Google text-embedding-004, and uploads to Supabase pgvector.
"""

import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from supabase import create_client, Client

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# ─── Configuration ───────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_TASK_TYPE = "RETRIEVAL_DOCUMENT"  # Optimized for document storage
TABLE_NAME = "knowledge_chunks"


def parse_knowledge_file(filepath: Path) -> list[dict]:
    """Parse a knowledge base markdown file into individual chunks."""
    content = filepath.read_text(encoding="utf-8")

    # Strip leading --- (first frontmatter delimiter at start of file)
    content = re.sub(r'^---\n', '', content)

    # Split on YAML frontmatter delimiters (---)
    # Each chunk starts with --- and ends before the next ---
    raw_chunks = re.split(r'\n---\n', content)

    chunks = []
    i = 0
    while i < len(raw_chunks):
        block = raw_chunks[i].strip()

        # Skip empty blocks
        if not block:
            i += 1
            continue

        # Check if this block is a YAML frontmatter block
        if block.startswith("concept_id:"):
            yaml_block = block
            # The next block should be the content
            if i + 1 < len(raw_chunks):
                content_block = raw_chunks[i + 1].strip()
                i += 2
            else:
                i += 1
                continue

            chunk = parse_single_chunk(yaml_block, content_block)
            if chunk:
                chunks.append(chunk)
        else:
            i += 1

    return chunks


def parse_single_chunk(yaml_text: str, content_text: str) -> dict | None:
    """Parse YAML frontmatter and markdown content into a structured dict."""
    try:
        # Parse YAML fields manually (simple key-value extraction)
        def extract_field(text: str, field: str) -> str:
            match = re.search(rf'^{field}:\s*(.+)$', text, re.MULTILINE)
            return match.group(1).strip() if match else ""

        def extract_list(text: str, field: str) -> list[str]:
            match = re.search(rf'^{field}:\s*\[(.+)\]$', text, re.MULTILINE)
            if match:
                items = match.group(1).split(",")
                return [item.strip().strip("'\"") for item in items]
            return []

        concept_id = extract_field(yaml_text, "concept_id")
        if not concept_id:
            return None

        domain = extract_field(yaml_text, "domain")
        jurisdiction = extract_field(yaml_text, "jurisdiction")
        audience = extract_field(yaml_text, "audience")
        tags = extract_list(yaml_text, "tags")

        # Extract title (### heading)
        title_match = re.search(r'^###\s+(.+)$', content_text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else concept_id

        # Extract semantic summary
        summary_match = re.search(
            r'\*\*Semantic Summary:\*\*\s*\n(.+?)(?=\n\n|\n\*\*)',
            content_text,
            re.DOTALL
        )
        semantic_summary = summary_match.group(1).strip() if summary_match else ""

        return {
            "concept_id": concept_id,
            "domain": domain,
            "jurisdiction": jurisdiction,
            "audience": audience,
            "tags": tags,
            "title": title,
            "semantic_summary": semantic_summary,
            "full_content": content_text,
        }
    except Exception as e:
        print(f"  ⚠️  Error parsing chunk: {e}")
        return None


def generate_embedding(client: genai.Client, text: str) -> list[float]:
    """Generate a 768-dim embedding via Google text-embedding-004."""
    # Combine semantic summary (primary) with full content for richer embedding
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config={
            "task_type": EMBEDDING_TASK_TYPE,
            "output_dimensionality": 768,
        },
    )
    return result.embeddings[0].values


def main():
    # ─── Validate environment ────────────────────────────────────
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY environment variable not set.")
        print("   Export it: export SUPABASE_SERVICE_KEY='your-service-role-key'")
        sys.exit(1)

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY environment variable not set.")
        print("   Export it: export GEMINI_API_KEY='your-gemini-api-key'")
        sys.exit(1)

    if not KNOWLEDGE_BASE_DIR.exists():
        print(f"❌ Knowledge base directory not found: {KNOWLEDGE_BASE_DIR}")
        sys.exit(1)

    # ─── Initialize clients ──────────────────────────────────────
    print("🔌 Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("🤖 Initializing Gemini embedding client...")
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

    # ─── Parse all knowledge base files ──────────────────────────
    md_files = sorted(KNOWLEDGE_BASE_DIR.glob("*.md"))
    print(f"\n📂 Found {len(md_files)} knowledge base files:")
    for f in md_files:
        print(f"   • {f.name}")

    all_chunks = []
    for filepath in md_files:
        chunks = parse_knowledge_file(filepath)
        print(f"   ✅ {filepath.name}: {len(chunks)} chunks parsed")
        all_chunks.extend(chunks)

    print(f"\n📊 Total chunks parsed: {len(all_chunks)}")

    # ─── Generate embeddings and upload ──────────────────────────
    print(f"\n🚀 Generating embeddings and uploading to Supabase...\n")

    success_count = 0
    error_count = 0

    for i, chunk in enumerate(all_chunks, 1):
        concept_id = chunk["concept_id"]
        try:
            # Create embedding text: combine summary + title for best retrieval
            embedding_text = f"{chunk['title']}. {chunk['semantic_summary']}"

            # Generate embedding
            embedding = generate_embedding(gemini_client, embedding_text)

            # Upsert to Supabase (insert or update if concept_id exists)
            row = {
                "concept_id": chunk["concept_id"],
                "domain": chunk["domain"],
                "jurisdiction": chunk["jurisdiction"],
                "audience": chunk["audience"],
                "tags": chunk["tags"],
                "title": chunk["title"],
                "semantic_summary": chunk["semantic_summary"],
                "full_content": chunk["full_content"],
                "embedding": embedding,
            }

            supabase.table(TABLE_NAME).upsert(
                row, on_conflict="concept_id"
            ).execute()

            print(f"   [{i:02d}/{len(all_chunks)}] ✅ {concept_id}")
            success_count += 1

            # Small delay to respect rate limits
            time.sleep(0.1)

        except Exception as e:
            print(f"   [{i:02d}/{len(all_chunks)}] ❌ {concept_id}: {e}")
            error_count += 1

    # ─── Summary ─────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"📊 Upload Complete!")
    print(f"   ✅ Successful: {success_count}")
    print(f"   ❌ Errors:     {error_count}")
    print(f"   📦 Total:      {len(all_chunks)}")
    print(f"{'='*50}")

    # ─── Verification query ──────────────────────────────────────
    print(f"\n🔍 Verification: Testing similarity search...")
    try:
        test_query = "What happens when my insurance denies a claim?"
        test_embedding = generate_embedding(gemini_client, test_query)

        # Use the search function we created
        result = supabase.rpc("search_knowledge", {
            "query_embedding": test_embedding,
            "match_count": 3,
        }).execute()

        if result.data:
            print(f"   Query: \"{test_query}\"")
            print(f"   Top 3 results:")
            for r in result.data:
                sim = r.get("similarity", 0)
                print(f"     • [{sim:.4f}] {r['title'][:80]}")
        else:
            print("   ⚠️  No results returned. Check the table and search function.")

    except Exception as e:
        print(f"   ⚠️  Verification query failed: {e}")
        print(f"   (This is OK — the data is uploaded. The search function can be tested later.)")


if __name__ == "__main__":
    main()
