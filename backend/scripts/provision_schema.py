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
    if not url:
        try:
            import sys
            sys.path.insert(0, str(REPO / "backend"))
            from app.config import settings
            url = settings.database_url
        except Exception:
            pass
    assert url, "DATABASE_URL is required"

    # asyncpg uses the standard scheme postgresql://; strip asyncpg prefix
    dsn = re.sub(r"^postgresql\+asyncpg://", "postgresql://", url)

    conn = await asyncpg.connect(dsn=dsn, statement_cache_size=0)

    tables = ["knowledge_chunks", "policy_chunks", "user_policies", "user_claims", "user_chats", "user_documents", "user_audits"]
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

    # ── Ensure user_id columns are uuid (not character varying) ─────────────
    # Older live databases may have been created with text/varchar user_id before
    # the migrations were corrected. This migration is idempotent — it is a no-op
    # when the column is already typed as uuid.
    print("\n== Ensuring user_id column types ==")
    for tbl in ["user_policies", "user_claims", "user_chats", "user_documents", "user_audits"]:
        try:
            row = await conn.fetchrow(
                """
                SELECT data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name=$1 AND column_name='user_id'
                """,
                tbl,
            )
            if row is None:
                print(f"  {tbl}.user_id: table or column missing — skip")
                continue
            if row["data_type"] == "uuid":
                print(f"  {tbl}.user_id: already uuid ✓")
                continue
            # Column exists but is text/varchar — delete any non-UUID rows then cast
            deleted = await conn.fetchval(
                f"DELETE FROM public.{tbl} WHERE user_id !~ "
                r"'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' "
                "RETURNING count(*)"
            )
            if deleted:
                print(f"  {tbl}: deleted {deleted} non-UUID row(s)")
            await conn.execute(
                f"ALTER TABLE public.{tbl} ALTER COLUMN user_id TYPE uuid USING user_id::uuid;"
            )
            print(f"  {tbl}.user_id: migrated {row['data_type']} → uuid ✓")
        except Exception as e:
            print(f"  {tbl}.user_id: migration error — {e}")

    # ── Re-apply RLS policies now that user_id is uuid everywhere ────────────
    rls_defs = [
        ("user_policies", "select", "USING",      "auth.uid() = user_id"),
        ("user_policies", "insert", "WITH CHECK",  "auth.uid() = user_id"),
        ("user_claims",   "select", "USING",       "auth.uid() = user_id"),
        ("user_claims",   "insert", "WITH CHECK",  "auth.uid() = user_id"),
        ("user_chats",    "select", "USING",       "auth.uid() = user_id"),
        ("user_chats",    "insert", "WITH CHECK",  "auth.uid() = user_id"),
        ("user_chats",    "update", "USING",       "auth.uid() = user_id"),
        ("user_documents", "select", "USING",      "auth.uid() = user_id"),
        ("user_documents", "insert", "WITH CHECK", "auth.uid() = user_id"),
        ("user_documents", "delete", "USING",      "auth.uid() = user_id"),
        ("user_audits",   "select", "USING",       "auth.uid() = user_id"),
        ("user_audits",   "insert", "WITH CHECK",  "auth.uid() = user_id"),
        ("user_audits",   "update", "USING",       "auth.uid() = user_id"),
        ("user_audits",   "delete", "USING",       "auth.uid() = user_id"),
    ]
    for tbl, op, clause, expr in rls_defs:
        pol = f'Users can {op} their {tbl.replace("user_", "")}'
        try:
            await conn.execute(f'DROP POLICY IF EXISTS "{pol}" ON public.{tbl};')
            for_clause = f"FOR {op.upper()} {clause} ({expr})"
            await conn.execute(
                f'CREATE POLICY "{pol}" ON public.{tbl} {for_clause};'
            )
        except Exception as e:
            print(f"  RLS {tbl} {op}: {e}")

    # ── Service-role grants (belt-and-suspenders) ─────────────────────────────
    for tbl in ["user_policies", "user_claims", "user_chats", "user_documents", "user_audits"]:
        try:
            await conn.execute(f"GRANT ALL ON TABLE public.{tbl} TO service_role;")
        except Exception as e:
            print(f"  GRANT {tbl}: {e}")

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
