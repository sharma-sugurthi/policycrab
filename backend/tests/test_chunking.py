import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import get_current_user
import json
import logging

logging.basicConfig(level=logging.INFO)

# Override auth dependency
app.dependency_overrides[get_current_user] = lambda: {"id": "test-user-123", "email": "test@example.com"}

client = TestClient(app)

def run_test():
    with open("test_policy_150.pdf", "rb") as f:
        print("Uploading 150-page PDF...")
        # Since policy chunking is async, using the TestClient will block until it completes
        response = client.post("/api/policy/upload-pdf", files={"file": ("test_policy_150.pdf", f, "application/pdf")})
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print("Response:", response.text)
            # Do not return early, still verify if chunks were inserted in Phase 1
            
        data = response.json()
        print("Upload Success:", data.get("success", False))
        print("Extracted Plan Name:", data.get("policy_profile", {}).get("plan_name"))
        
        print("\n--- Verifying Vector Retrieval ---")
        # Let's call the policy analyzer to see if it retrieves the specific clause
        # The analyzer needs a session_id and a claim case
        # Wait, the upload response doesn't return session_id in the /upload endpoint directly.
        # But we can query Supabase directly to check.
        session_id = data.get("session_id") # Actually not returned in PolicyUploadResponse
        # Let's import the supabase client and search it directly.
        import asyncio
        from app.services.supabase_client import get_supabase_client
        from app.services.llm_router import generate_embedding
        
        async def check_search():
            db = get_supabase_client()
            # We can find the session_id by finding the latest chunks
            result = db.table("policy_chunks").select("session_id").limit(1).execute()
            if not result.data:
                print("No chunks found in DB!")
                return
                
            found_session_id = result.data[0]["session_id"]
            print(f"Testing search for session: {found_session_id}")
            
            from app.services.supabase_client import search_policy_document
            
            # Query 1: Find the emergency appendectomy waiver (Page 42)
            query1 = "emergency appendectomy prior authorization waiver"
            emb1 = await generate_embedding(query1)
            res1 = await search_policy_document(found_session_id, emb1, match_count=3, similarity_threshold=0.2)
            
            print(f"\nQuery: '{query1}'")
            for r in res1:
                print(f"Page {r['page_number']}: {r['chunk_text'][:100]}... (Sim: {r.get('similarity', 0):.2f})")
                
            # Query 2: Find the cosmetic surgery exclusion (Page 100)
            query2 = "cosmetic surgery exclusion out of network"
            emb2 = await generate_embedding(query2)
            res2 = await search_policy_document(found_session_id, emb2, match_count=3, similarity_threshold=0.2)
            
            print(f"\nQuery: '{query2}'")
            for r in res2:
                print(f"Page {r['page_number']}: {r['chunk_text'][:100]}... (Sim: {r.get('similarity', 0):.2f})")
                
            # Query 3: Find the appeal deadline (Page 149)
            query3 = "how many days to appeal a denial"
            emb3 = await generate_embedding(query3)
            res3 = await search_policy_document(found_session_id, emb3, match_count=3, similarity_threshold=0.2)
            
            print(f"\nQuery: '{query3}'")
            for r in res3:
                print(f"Page {r['page_number']}: {r['chunk_text'][:100]}... (Sim: {r.get('similarity', 0):.2f})")

        asyncio.run(check_search())

if __name__ == "__main__":
    run_test()
