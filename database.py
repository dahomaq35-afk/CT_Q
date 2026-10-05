# =========================================================
# CT QURAN BOT
# database.py
# =========================================================

import os
import sqlite3
from datetime import datetime, timezone


# =========================================================
# PATHS
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")

DB_FILE = os.path.join(DATA_DIR, "quran_bot.db")


# =========================================================
# DATABASE SETUP
# =========================================================

def ensure_data_directory():
    os.makedirs(DATA_DIR, exist_ok=True)


def get_connection():
    ensure_data_directory()

    connection = sqlite3.connect(
        DB_FILE,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def init_db():

    connection = get_connection()

    cursor = connection.cursor()

    # -----------------------------------------------------
    # SERVER SETTINGS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            voice_channel_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # PLAY HISTORY
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS play_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            source TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            rejected INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # REJECTED ATTEMPTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rejected_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            url TEXT NOT NULL,
            reason TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # QUEUE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            source TEXT,
            position INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


# =========================================================
# TIME
# =========================================================

def now():

    return datetime.now(
        timezone.utc
    ).isoformat()


# =========================================================
# VOICE CHANNEL SETTINGS
# =========================================================

def set_voice_channel(
    guild_id: int,
    voice_channel_id: int
):

    connection = get_connection()

    cursor = connection.cursor()

    timestamp = now()

    cursor.execute("""
        INSERT INTO guild_settings (
            guild_id,
            voice_channel_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(guild_id)
        DO UPDATE SET
            voice_channel_id = excluded.voice_channel_id,
            updated_at = excluded.updated_at
    """, (
        guild_id,
        voice_channel_id,
        timestamp,
        timestamp
    ))

    connection.commit()
    connection.close()


def get_voice_channel(
    guild_id: int
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT voice_channel_id
        FROM guild_settings
        WHERE guild_id = ?
    """, (guild_id,))

    row = cursor.fetchone()

    connection.close()

    if not row:
        return None

    return row["voice_channel_id"]


# =========================================================
# PLAY HISTORY
# =========================================================

def add_play_history(
    guild_id: int,
    user_id: int,
    username: str,
    url: str,
    title: str = "",
    source: str = "",
    verified: bool = False,
    rejected: bool = False
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO play_history (
            guild_id,
            user_id,
            username,
            url,
            title,
            source,
            verified,
            rejected,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        guild_id,
        user_id,
       
