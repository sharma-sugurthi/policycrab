"""
One-time script to seed the knowledge_chunks table with core regulatory
facts about US health insurance. This expands the RAG capability (Layer 2)
so the agent has dense, authoritative context for specific legal scenarios.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add backend directory to sys.path so we can import app modules
backend_dir = str(Path(__file__).parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.llm_router import generate_embeddings_batch
from app.services.supabase_client import get_supabase_client

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# List of highly authoritative facts extracted from cms.gov and dol.gov
SEED_DATA = [
    {
        "concept_id": "ACA-TIMELINES-01",
        "title": "ACA Internal Appeal and External Review Timelines",
        "semantic_summary": (
            "Under the Affordable Care Act (ACA), for non-grandfathered plans, individuals have 180 days from the "
            "receipt of a denial (Adverse Benefit Determination) to file an internal appeal. If the internal appeal "
            "is denied, they have 4 months to request an external review."
        ),
        "source_url": "https://www.cms.gov/CCIIO/Programs-and-Initiatives/Consumer-Support-and-Information/External-Appeals",
        "domain": "ACA",
        "jurisdiction": "FEDERAL",
        "audience": "GENERAL",
        "tags": ["deadlines", "aca", "appeals"]
    },
    {
        "concept_id": "ERISA-CLAIMS-01",
        "title": "ERISA Claims Procedure Regulations (29 CFR 2560.503-1)",
        "semantic_summary": (
            "Under ERISA section 503, group health plans must give claimants at least 180 days following receipt of "
            "an adverse benefit determination to appeal. For urgent care claims, the plan must notify the claimant "
            "of its decision as soon as possible, taking into account the medical exigencies, but not later than "
            "72 hours after receipt of the claim."
        ),
        "source_url": "https://www.dol.gov/agencies/ebsa/laws-and-regulations/laws/erisa",
        "domain": "ERISA",
        "jurisdiction": "FEDERAL",
        "audience": "GENERAL",
        "tags": ["deadlines", "erisa", "appeals"]
    },
    {
        "concept_id": "NSA-CONSUMER-01",
        "title": "No Surprises Act Consumer Protections",
        "semantic_summary": (
            "The No Surprises Act protects consumers from surprise medical bills for emergency services, air ambulance "
            "services provided by out-of-network providers, and non-emergency services provided by out-of-network "
            "providers at in-network facilities. Patients cannot be billed for more than their in-network cost-sharing "
            "amounts for these services."
        ),
        "source_url": "https://www.cms.gov/nosurprises",
        "domain": "NSA",
        "jurisdiction": "FEDERAL",
        "audience": "GENERAL",
        "tags": ["nsa", "billing", "surprise-billing"]
    },
    {
        "concept_id": "MEDICARE-APPEALS-01",
        "title": "Medicare Original (Part A & B) Appeal Process",
        "semantic_summary": (
            "The Medicare fee-for-service appeal process has 5 levels. Level 1 is Redetermination by a Medicare "
            "Administrative Contractor (MAC). The request must be filed within 120 days from the date of receipt "
            "of the initial determination (Medicare Summary Notice)."
        ),
        "source_url": "https://www.cms.gov/Medicare/Appeals-and-Grievances/OrgMedFFSAppeals",
        "domain": "MEDICARE",
        "jurisdiction": "FEDERAL",
        "audience": "GENERAL",
        "tags": ["deadlines", "medicare", "appeals"]
    }
]


async def seed_database():
    logger.info(f"Preparing to seed {len(SEED_DATA)} knowledge concepts...")
    
    # 1. Generate embeddings in a batch
    texts_to_embed = [
        f"Title: {item['title']}\nSummary: {item['semantic_summary']}"
        for item in SEED_DATA
    ]
    
    logger.info("Generating embeddings using Vertex AI (Gemini)...")
    try:
        embeddings = await generate_embeddings_batch(texts_to_embed)
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        return
        
    if not embeddings or len(embeddings) != len(SEED_DATA):
        logger.error("Embedding count mismatch.")
        return
        
    # 2. Insert into Supabase
    client = get_supabase_client()
    rows_to_insert = []
    
    for i, item in enumerate(SEED_DATA):
        rows_to_insert.append({
            "concept_id": item["concept_id"],
            "title": item["title"],
            "semantic_summary": item["semantic_summary"],
            "embedding": embeddings[i],
            "domain": item["domain"],
            "jurisdiction": item["jurisdiction"],
            "audience": item["audience"],
            "tags": item["tags"],
            "full_content": item["semantic_summary"]
        })
        
    logger.info(f"Inserting {len(rows_to_insert)} rows into knowledge_chunks table...")
    try:
        # Assuming on_conflict="concept_id" if we set up a unique constraint,
        # but the table schema might not have it. Standard upsert behavior applies.
        result = client.table("knowledge_chunks").upsert(rows_to_insert, on_conflict="concept_id").execute()
        inserted = len(result.data) if result.data else 0
        logger.info(f"Successfully seeded {inserted} concepts into the knowledge base!")
    except Exception as e:
        logger.error(f"Failed to insert into Supabase: {e}")


if __name__ == "__main__":
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"):
        logger.warning("Supabase credentials not found in environment. Please load .env variables before running.")
        
    asyncio.run(seed_database())
