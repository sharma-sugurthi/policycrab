"""Inspect live Supabase schema and apply missing pieces from `supabase/migrations/*.sql`.

Connects to DATABASE_URL via asyncpg, prints what's present, applies each
migration file as `IF NOT EXISTS`-safe DDL, then issues the standard
PostgREST schema-cache refresh so newly added columns become visible to the API.
"""
import asyncio
import os
import pathlib
import re
import asyncpg


REPO = pathlib.Path(__file__).resolve().parents[2]
MIG_DIR = REPO / "supabase" / "migrations"
EXTRA_DIR = REPO / "backend" / "scripts" / "migrations"

# SQL helpers we don't want the executor to try as individual statements.
NOTIFY_RELOAD = "NOTIFY pgrst, 'reload schema';"


async def columns_for(conn, table: str) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )
    return [r["column_name"] for r in rows]


async def main() -> None:
    url = os.environ.get("DATABASE_URL")
    assert url, "DATABASE_URL is required"

    # asyncpg uses the standard scheme postgresql://; strip asyncpg prefix
    dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)

    conn = await asyncpg.connect(dsn=dsn, statement_cache_size=0)

    tables = ["knowledge_chunks", "policy_chunks", "user_policies", "user_claims", "user_chats"]
    print("== State before ==")
    for t in tables:
        try:
            cols = await columns_for(conn, t)
            print(f"  {t}: cols={cols}")
        except Exception as e:
            print(f"  {t}: MISSING ({e})")

    migrations = sorted(MIG_DIR.glob("*.sql")) + sorted(EXTRA_DIR.glob("*.sql"))
    print("\n== Applying migrations ==")
    for path in migrations:
        sql = path.read_text()
        print(f"  → {path.relative_to(REPO)} ({len(sql)} bytes)")
        try:
            await conn.execute(sql)
        except Exception as e:
            print(f"     !! error: {e}")

    print(f"\n== Refreshing PostgREST schema cache: {NOTIFY_RELOAD}")
    try:
        await conn.execute(NOTIFY_RELOAD)
        print("  notified ✓")
    except Exception as e:
        print(f"  notify failed (often harmless): {e}")

    print("\n== State after ==")
    for t in tables:
        try:
            cols = await columns_for(conn, t)
            print(f"  {t}: cols={cols}")
        except Exception as e:
            print(f"  {t}: MISSING ({e})")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
