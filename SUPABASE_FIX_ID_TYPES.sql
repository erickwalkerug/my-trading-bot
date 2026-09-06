-- KETS SUPABASE ID FIX
-- IMPORTANT: This keeps the bot's existing trading rules unchanged.
-- It fixes the PostgreSQL error:
-- "identity column type must be smallint, integer, or bigint"
--
-- The bot generates string IDs such as GOLD-BUY-<milliseconds> and
-- BTC-SELL-<milliseconds>, so these columns must be TEXT.

BEGIN;

-- signals.id
ALTER TABLE IF EXISTS public.signals
  ALTER COLUMN id DROP IDENTITY IF EXISTS;

ALTER TABLE IF EXISTS public.signals
  ALTER COLUMN id DROP DEFAULT;

ALTER TABLE IF EXISTS public.signals
  ALTER COLUMN id TYPE text USING id::text;

-- engine_history.id
ALTER TABLE IF EXISTS public.engine_history
  ALTER COLUMN id DROP IDENTITY IF EXISTS;

ALTER TABLE IF EXISTS public.engine_history
  ALTER COLUMN id DROP DEFAULT;

ALTER TABLE IF EXISTS public.engine_history
  ALTER COLUMN id TYPE text USING id::text;

COMMIT;

-- Verify
SELECT table_name, column_name, data_type, is_identity
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('signals', 'engine_history')
  AND column_name = 'id'
ORDER BY table_name;
