KETS FIXED BOT
================

1. Keep the Render Start Command as:
   python -u bot.py

2. In Supabase SQL Editor, run:
   SUPABASE_FIX_ID_TYPES.sql
   (or run the complete supabase_schema.sql)

3. This fixes the bigint/text signal-ID error.

MARKET SCHEDULE
---------------
Monday-Friday: GOLD (XAU/USD) ONLY
Saturday-Sunday: BTC (BTC/USD) ONLY

The bot remains on a 1-minute scan interval and the existing KETS website
signal delivery is unchanged.


SUPABASE ID FIX:
If Supabase previously reported "identity column type must be smallint,
integer, or bigint", run SUPABASE_FIX_ID_TYPES.sql. The migration first
removes the identity/default from the legacy numeric id columns and then
converts them to TEXT so the bot's string signal IDs are accepted.

TRADING RULES PRESERVED:
- Monday-Friday: GOLD (XAU/USD) ONLY
- Saturday-Sunday: BTC (BTC/USD) ONLY
- 1-minute candles
- scan every 1 minute
- 06:00-18:00 EAT
No strategy rules were changed by this fix.
