-- Enable multiple chat threads per user
-- Drop the unique constraint that limits a user to 1 chat thread
ALTER TABLE public.user_chats DROP CONSTRAINT IF EXISTS user_chats_user_id_key;

-- Add title column for thread names
ALTER TABLE public.user_chats ADD COLUMN IF NOT EXISTS title text;
