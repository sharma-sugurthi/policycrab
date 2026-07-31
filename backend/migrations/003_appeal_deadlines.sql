-- ============================================================
-- Supabase Migration: Create appeal_deadlines table
-- Feature: Statutory Deadline Tracker (Carrier Routing Hub)
-- Date: 2026-07-31
-- ============================================================

-- Create the appeal_deadlines table
CREATE TABLE IF NOT EXISTS appeal_deadlines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  carrier_name TEXT NOT NULL,
  appeal_level TEXT NOT NULL,
  appeal_framework TEXT NOT NULL,
  state_code TEXT NOT NULL DEFAULT 'XX',
  date_denial_received DATE NOT NULL,
  date_appeal_filed DATE,
  deadline_date DATE NOT NULL,
  statutory_days INT NOT NULL DEFAULT 180,
  insurer_response_deadline DATE,
  insurer_response_days INT DEFAULT 30,
  notes TEXT,
  claim_summary TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE appeal_deadlines ENABLE ROW LEVEL SECURITY;

-- RLS Policies: Users can only CRUD their own deadlines
CREATE POLICY "Users can view own deadlines" ON appeal_deadlines
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own deadlines" ON appeal_deadlines
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own deadlines" ON appeal_deadlines
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own deadlines" ON appeal_deadlines
  FOR DELETE USING (auth.uid() = user_id);

-- Index for fast user-scoped lookups
CREATE INDEX idx_appeal_deadlines_user_id ON appeal_deadlines(user_id);

-- Optional: auto-update the updated_at column on row changes
CREATE OR REPLACE FUNCTION update_appeal_deadlines_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_appeal_deadlines_updated_at
  BEFORE UPDATE ON appeal_deadlines
  FOR EACH ROW
  EXECUTE FUNCTION update_appeal_deadlines_updated_at();
