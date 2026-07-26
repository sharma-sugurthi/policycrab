from app.services.supabase_client import get_supabase_client

client = get_supabase_client()
for t in ['knowledge_chunks', 'policy_chunks', 'user_policies', 'user_claims', 'user_chats']:
    try:
        r = client.table(t).select('id', count='exact').limit(1).execute()
        print(f'  {t}: rows={r.count}')
    except Exception as e:
        msg = str(e).replace('\n', ' ')[:200]
        print(f'  {t}: MISSING -> {msg}')

# Also test the policy_chunks RPC
from app.services.supabase_client import search_policy_document
try:
    r = await_search = None  # not actually awaited, just probe symbol exists
    print('  search_policy_document RPC symbol: importable')
except Exception as e:
    print(f'  search_policy_document: {e}')
