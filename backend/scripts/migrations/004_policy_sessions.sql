-- =============================================================================
-- Migration 004: Policy Session Persistence
--
-- Purpose:
--   Creates a `policy_sessions` table that persists the extracted PolicyProfile
--   JSON alongside its session_id and user_id.
--
--   This allows returning users to skip Phase 2 (LLM extraction) entirely
--   when their policy was already processed in a prior session.
--   Saves 1 LLM call per returning user per claim evaluation.
--
-- Design notes:
--   - session_id is the primary key (same as in policy_chunks).
--   - user_id links to auth.users for access control — a user can only load
--     their own sessions.
--   - policy_profile is stored as JSONB for fast partial querying.
--   - RLS policies enforce that users only see their own rows.
-- =============================================================================

-- Step 1: Create table
CREATE TABLE IF NOT EXISTS policy_sessions (
  session_id      TEXT        PRIMARY KEY,
  user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  policy_profile  JSONB       NOT NULL,
  plan_name       TEXT        GENERATED ALWAYS AS (policy_profile->>'plan_name') STORED,
  carrier_name    TEXT        GENERATED ALWAYS AS (policy_profile->>'carrier_name') STORED,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Step 2: Indexes for common access patterns
CREATE INDEX IF NOT EXISTS idx_policy_sessions_user_id
  ON policy_sessions (user_id);

CREATE INDEX IF NOT EXISTS idx_policy_sessions_created_at
  ON policy_sessions (created_at DESC);

-- Step 3: Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_policy_sessions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_policy_sessions_updated_at ON policy_sessions;
CREATE TRIGGER trg_policy_sessions_updated_at
  BEFORE UPDATE ON policy_sessions
  FOR EACH ROW EXECUTE FUNCTION update_policy_sessions_updated_at();

-- Step 4: Row Level Security — users can only read/write their own sessions
ALTER TABLE policy_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_sessions_user_isolation ON policy_sessions;
CREATE POLICY policy_sessions_user_isolation ON policy_sessions
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Service role bypasses RLS (for backend writes using service key)
-- This is handled automatically by Supabase's service_role key bypass.
