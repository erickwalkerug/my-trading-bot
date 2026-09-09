KETS Render storage
===================
The bot prefers /var/data/kets_bot.db when a Render Persistent Disk is mounted.
It automatically creates the directory and checks write access.

If /var/data is unavailable or not writable, the bot falls back to:
    /tmp/kets-data/kets_bot.db

This fallback prevents the service from crashing on startup. The /tmp filesystem
is ephemeral, so true persistence requires a Render Persistent Disk mounted at
/var/data (or another persistent storage service).

The SQLite error:
    sqlite3.OperationalError: unable to open database file
is therefore handled by the included startup-safe storage code.
