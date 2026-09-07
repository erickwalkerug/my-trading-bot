KETS TRADING BOT — RENDER PERSISTENT STORAGE

Storage: SQLite database on Render Persistent Disk at /var/data/kets_bot.db.
The KETS strategy is unchanged.

Render disk:
- Mount path: /var/data
- Database: /var/data/kets_bot.db
- Retention: 7 days for signals and engine history

Required Render variables:
- KETS_API_KEY
- KETS_SIGNAL_SOURCE_URL
- KETS_SIGNAL_SOURCE_KEY

No Supabase database credentials are required for the bot.
