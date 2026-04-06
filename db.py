import sqlite3
import os
from config import DB_PATH, UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT DEFAULT '',
                telegram TEXT DEFAULT '',
                service TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                currency TEXT DEFAULT 'EUR',
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                comment TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                reminder_24h INTEGER DEFAULT 0,
                reminder_2h_sent INTEGER DEFAULT 0,
                followup_sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                caption TEXT DEFAULT '',
                category TEXT DEFAULT 'Sonstiges',
                sort_order INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS google_tokens (
                id INTEGER PRIMARY KEY,
                token_data TEXT NOT NULL,
                updated_at TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blocked_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                reason TEXT DEFAULT ''
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS working_hours (
                weekday INTEGER PRIMARY KEY,
                is_open INTEGER DEFAULT 1,
                open_hour INTEGER DEFAULT 10,
                close_hour INTEGER DEFAULT 20
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blocked_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                reason TEXT DEFAULT '',
                UNIQUE(date, time)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT DEFAULT '',
                media_url TEXT DEFAULT '',
                media_type TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Migrations
        for col in [
            "ALTER TABLE appointments ADD COLUMN reminder_2h_sent INTEGER DEFAULT 0",
            "ALTER TABLE appointments ADD COLUMN followup_sent INTEGER DEFAULT 0",
            "ALTER TABLE appointments ADD COLUMN google_event_id TEXT DEFAULT ''",
            "ALTER TABLE photos ADD COLUMN category TEXT DEFAULT 'Sonstiges'",
            "ALTER TABLE posts ADD COLUMN media_extra TEXT DEFAULT '[]'",
        ]:
            try:
                conn.execute(col)
            except Exception:
                pass

        if conn.execute('SELECT COUNT(*) FROM working_hours').fetchone()[0] == 0:
            conn.executemany(
                'INSERT INTO working_hours (weekday, is_open, open_hour, close_hour) VALUES (?,?,?,?)',
                [(0,0,10,20),(1,1,10,20),(2,1,10,20),(3,1,10,20),(4,1,10,20),(5,1,9,18),(6,0,10,20)]
            )
        conn.commit()


def get_setting(key, default=''):
    try:
        with get_db() as conn:
            row = conn.execute('SELECT value FROM admin_settings WHERE key=?', (key,)).fetchone()
            return row['value'] if row and row['value'] else default
    except Exception:
        return default


def set_setting(key, value):
    with get_db() as conn:
        conn.execute(
            'INSERT INTO admin_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
            (key, value)
        )
        conn.commit()
