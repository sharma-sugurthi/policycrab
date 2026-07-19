from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

try:
    result = client.models.embed_content(
        model="text-embedding-004",
        contents=["test text", "another one"],
        config={
            "task_type": "RETRIEVAL_DOCUMENT",
            "output_dimensionality": 768,
        },
    )
    print("Success")
    print(len(result.embeddings))
except Exception as e:
    import traceback
    traceback.print_exc()
