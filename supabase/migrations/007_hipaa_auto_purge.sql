-- Enable pg_cron extension if it's not already enabled
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Create a function to delete records older than 30 days for data minimization and privacy
CREATE OR REPLACE FUNCTION purge_hipaa_records_after_30_days()
RETURNS void AS $$
BEGIN
  -- 1. Purge old raw EOB/Document extractions
  DELETE FROM public.user_documents
  WHERE created_at < NOW() - INTERVAL '30 days';

  -- 2. Purge old medical bill audits
  DELETE FROM public.user_audits
  WHERE created_at < NOW() - INTERVAL '30 days';
  
  -- Note: user_policies and user_claims are intentionally kept as active 
  -- profile history, unless the user explicitly deletes their account.
END;
$$ LANGUAGE plpgsql;

-- Schedule the job to run daily at midnight
SELECT cron.schedule('privacy-data-purge', '0 0 * * *', $$
  SELECT purge_hipaa_records_after_30_days();
$$);
