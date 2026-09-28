"""
MedQuiz AI - Asynchronous SQLite Database Layer
Provides connection management and CRUD operations for all application entities.
"""

import aiosqlite
from contextlib import asynccontextmanager
from datetime import datetime, date
from typing import Any, Optional
from config import DB_PATH, ADMIN_IDS
from utils.logger import logger


@asynccontextmanager
async def get_db():
    """Provides a safely managed aiosqlite database connection."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()

# Alias for external modules
get_db_connection = get_db


async def init_db() -> None:
    """Initializes tables, indexes, and default settings in the database."""
    async with get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS destinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                type TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT,
                difficulty TEXT NOT NULL,
                language TEXT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option INTEGER NOT NULL,
                explanation TEXT NOT NULL,
                question_hash TEXT UNIQUE NOT NULL,
                telegram_message_id INTEGER,
                telegram_poll_id TEXT,
                destination_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'generated'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT DEFAULT 'Random',
                difficulty TEXT DEFAULT 'Medium',
                language TEXT DEFAULT 'English',
                post_time TEXT NOT NULL,
                post_days TEXT DEFAULT 'all',
                enabled INTEGER DEFAULT 1,
                last_run_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (destination_id) REFERENCES destinations (id) ON DELETE CASCADE
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS ai_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success INTEGER DEFAULT 1,
                error_msg TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, name)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast lookup
        await db.execute("CREATE INDEX IF NOT EXISTS idx_question_hash ON questions(question_hash)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_question_created ON questions(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(enabled)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ai_usage_timestamp ON ai_usage(timestamp)")

        # Sync .env ADMIN_IDS into admins table
        for aid in ADMIN_IDS:
            await db.execute(
                "INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)",
                (aid, "Config Admin")
            )

        # Initialize default settings if not existing
        defaults = {
            "default_language": "English",
            "default_difficulty": "Medium",
            "send_header": "true",
            "send_explanation": "true",
            "ai_model": "meta-llama/llama-3.1-8b-instruct:free",
            "ai_temperature": "0.7",
            "ai_max_tokens": "1000",
            "verification_enabled": "true"
        }
        for k, v in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v)
            )

        await db.commit()
    logger.info("Database initialized successfully.")


# ==========================================
# ADMIN OPERATIONS
# ==========================================

async def is_admin(user_id: int) -> bool:
    """Checks if a user is an authorized admin."""
    if user_id in ADMIN_IDS:
        return True
    async with get_db() as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def add_admin(user_id: int, username: Optional[str] = None) -> bool:
    """Adds a new admin by user_id."""
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)",
                (user_id, username or f"Admin_{user_id}")
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding admin {user_id}: {e}")
        return False


async def get_all_admins() -> list[dict[str, Any]]:
    """Retrieves all registered admins."""
    async with get_db() as db:
        async with db.execute("SELECT user_id, username, added_at FROM admins ORDER BY added_at ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ==========================================
# DESTINATIONS (CHANNELS / GROUPS)
# ==========================================

async def add_destination(chat_id: str, title: str, dest_type: str = "channel") -> tuple[bool, str]:
    """Adds a channel or group destination."""
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO destinations (chat_id, title, type, enabled) VALUES (?, ?, ?, 1)",
                (str(chat_id), title, dest_type)
            )
            await db.commit()
            return True, "Destination added successfully."
    except aiosqlite.IntegrityError:
        return False, "This channel/group is already registered."
    except Exception as e:
        logger.error(f"Failed to add destination {chat_id}: {e}")
        return False, str(e)


async def remove_destination(dest_id: int) -> bool:
    """Deletes a destination and its associated schedules."""
    try:
        async with get_db() as db:
            await db.execute("DELETE FROM schedules WHERE destination_id = ?", (dest_id,))
            await db.execute("DELETE FROM destinations WHERE id = ?", (dest_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error removing destination {dest_id}: {e}")
        return False


async def toggle_destination(dest_id: int) -> Optional[bool]:
    """Toggles enabled/disabled state of a destination."""
    async with get_db() as db:
        async with db.execute("SELECT enabled FROM destinations WHERE id = ?", (dest_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            new_state = 0 if row["enabled"] else 1
            await db.execute("UPDATE destinations SET enabled = ? WHERE id = ?", (new_state, dest_id))
            await db.commit()
            return bool(new_state)


async def get_destinations(only_enabled: bool = False) -> list[dict[str, Any]]:
    """Fetches all registered destinations."""
    query = "SELECT * FROM destinations"
    if only_enabled:
        query += " WHERE enabled = 1"
    query += " ORDER BY id DESC"
    async with get_db() as db:
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_destination_by_id(dest_id: int) -> Optional[dict[str, Any]]:
    """Fetches a specific destination by primary key ID."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM destinations WHERE id = ?", (dest_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ==========================================
# QUESTIONS
# ==========================================

async def save_question(
    category: str,
    subject: str,
    topic: str,
    difficulty: str,
    language: str,
    question: str,
    options: list[str],
    correct_option: int,
    explanation: str,
    question_hash: str,
    destination_id: Optional[int] = None,
    status: str = "generated"
) -> Optional[int]:
    """Saves a new question into the database and returns its new ID."""
    try:
        async with get_db() as db:
            cursor = await db.execute("""
                INSERT INTO questions (
                    category, subject, topic, difficulty, language,
                    question, option_a, option_b, option_c, option_d,
                    correct_option, explanation, question_hash,
                    destination_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                category, subject, topic, difficulty, language,
                question, options[0], options[1], options[2], options[3],
                correct_option, explanation, question_hash,
                destination_id, status
            ))
            await db.commit()
            return cursor.lastrowid
    except aiosqlite.IntegrityError:
        logger.warning(f"Duplicate question detected with hash {question_hash}")
        return None
    except Exception as e:
        logger.error(f"Error saving question: {e}")
        return None


async def update_question_post_status(
    question_id: int,
    status: str,
    telegram_message_id: Optional[int] = None,
    telegram_poll_id: Optional[str] = None,
    destination_id: Optional[int] = None
) -> bool:
    """Updates publication status and Telegram IDs for a question."""
    try:
        async with get_db() as db:
            await db.execute("""
                UPDATE questions
                SET status = ?, telegram_message_id = ?, telegram_poll_id = ?, destination_id = COALESCE(?, destination_id)
                WHERE id = ?
            """, (status, telegram_message_id, telegram_poll_id, destination_id, question_id))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating question {question_id} status: {e}")
        return False


async def get_question_by_hash(question_hash: str) -> Optional[dict[str, Any]]:
    """Looks up a question by normalized SHA-256 hash."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM questions WHERE question_hash = ?", (question_hash,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_question_by_id(question_id: int) -> Optional[dict[str, Any]]:
    """Looks up a question by primary key ID."""
    async with get_db() as db:
        async with db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_recent_questions(limit: int = 100) -> list[dict[str, Any]]:
    """Returns recent questions for similarity checking."""
    async with get_db() as db:
        async with db.execute(
            "SELECT id, question, question_hash FROM questions ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_question_history(page: int = 1, page_size: int = 5) -> tuple[list[dict[str, Any]], int]:
    """Retrieves paginated question history along with total count."""
    offset = (page - 1) * page_size
    async with get_db() as db:
        async with db.execute("SELECT COUNT(*) as total FROM questions") as cursor:
            total = (await cursor.fetchone())["total"]

        async with db.execute("""
            SELECT q.*, d.title as destination_title
            FROM questions q
            LEFT JOIN destinations d ON q.destination_id = d.id
            ORDER BY q.id DESC
            LIMIT ? OFFSET ?
        """, (page_size, offset)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows], total


# ==========================================
# SCHEDULES
# ==========================================

async def add_schedule(
    destination_id: int,
    category: str,
    subject: str,
    topic: str,
    difficulty: str,
    language: str,
    post_time: str,
    post_days: str = "all"
) -> Optional[int]:
    """Creates a new automated posting schedule."""
    try:
        async with get_db() as db:
            cursor = await db.execute("""
                INSERT INTO schedules (
                    destination_id, category, subject, topic, difficulty,
                    language, post_time, post_days, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                destination_id, category, subject, topic, difficulty,
                language, post_time, post_days
            ))
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error adding schedule: {e}")
        return None


async def get_schedules(only_enabled: bool = False) -> list[dict[str, Any]]:
    """Retrieves schedules joined with destination details."""
    query = """
        SELECT s.*, d.title as destination_title, d.chat_id as destination_chat_id
        FROM schedules s
        JOIN destinations d ON s.destination_id = d.id
    """
    if only_enabled:
        query += " WHERE s.enabled = 1 AND d.enabled = 1"
    query += " ORDER BY s.post_time ASC"

    async with get_db() as db:
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_schedule_by_id(schedule_id: int) -> Optional[dict[str, Any]]:
    """Retrieves a single schedule by ID."""
    async with get_db() as db:
        async with db.execute("""
            SELECT s.*, d.title as destination_title, d.chat_id as destination_chat_id
            FROM schedules s
            JOIN destinations d ON s.destination_id = d.id
            WHERE s.id = ?
        """, (schedule_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def toggle_schedule(schedule_id: int) -> Optional[bool]:
    """Pauses or resumes a schedule."""
    async with get_db() as db:
        async with db.execute("SELECT enabled FROM schedules WHERE id = ?", (schedule_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            new_state = 0 if row["enabled"] else 1
            await db.execute("UPDATE schedules SET enabled = ? WHERE id = ?", (new_state, schedule_id))
            await db.commit()
            return bool(new_state)


async def delete_schedule(schedule_id: int) -> bool:
    """Deletes a posting schedule."""
    try:
        async with get_db() as db:
            await db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error deleting schedule {schedule_id}: {e}")
        return False


async def update_schedule_last_run(schedule_id: int) -> None:
    """Updates the last_run_at timestamp for a schedule."""
    async with get_db() as db:
        await db.execute(
            "UPDATE schedules SET last_run_at = CURRENT_TIMESTAMP WHERE id = ?",
            (schedule_id,)
        )
        await db.commit()


# ==========================================
# SETTINGS
# ==========================================

async def get_setting(key: str, default: str = "") -> str:
    """Reads a setting value by key."""
    async with get_db() as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    """Upserts a setting key-value pair."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value))
        )
        await db.commit()


async def get_all_settings() -> dict[str, str]:
    """Retrieves all application settings."""
    async with get_db() as db:
        async with db.execute("SELECT key, value FROM settings") as cursor:
            rows = await cursor.fetchall()
            return {r["key"]: r["value"] for r in rows}


# ==========================================
# AI USAGE & RATE LIMITING
# ==========================================

async def record_ai_usage(model: str, tokens: int, success: bool = True, error_msg: Optional[str] = None) -> None:
    """Logs an AI generation request."""
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO ai_usage (model, tokens_used, success, error_msg) VALUES (?, ?, ?, ?)",
                (model, tokens, 1 if success else 0, error_msg)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to record AI usage: {e}")


async def get_ai_usage_in_window(hours: int = 1) -> int:
    """Calculates number of AI calls in the last N hours."""
    async with get_db() as db:
        async with db.execute(
            "SELECT COUNT(*) as count FROM ai_usage WHERE timestamp >= datetime('now', '-' || ? || ' hours')",
            (hours,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["count"] if row else 0


# ==========================================
# CUSTOM SUBJECTS
# ==========================================

async def add_custom_subject(category: str, name: str) -> bool:
    """Adds a custom subject to a category."""
    try:
        async with get_db() as db:
            await db.execute(
                "INSERT INTO custom_subjects (category, name) VALUES (?, ?)",
                (category, name.strip())
            )
            await db.commit()
            return True
    except Exception as e:
        logger.warning(f"Could not add custom subject {name}: {e}")
        return False


async def get_custom_subjects(category: Optional[str] = None) -> list[dict[str, Any]]:
    """Lists custom subjects, optionally filtered by category."""
    query = "SELECT * FROM custom_subjects"
    params = ()
    if category:
        query += " WHERE category = ?"
        params = (category,)
    query += " ORDER BY name ASC"

    async with get_db() as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_custom_subject(subject_id: int) -> bool:
    """Removes a custom subject."""
    try:
        async with get_db() as db:
            await db.execute("DELETE FROM custom_subjects WHERE id = ?", (subject_id,))
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Error deleting custom subject {subject_id}: {e}")
        return False


# ==========================================
# DASHBOARD & STATISTICS
# ==========================================

async def get_dashboard_stats() -> dict[str, Any]:
    """Computes comprehensive statistics for the admin dashboard."""
    stats: dict[str, Any] = {}

    async with get_db() as db:
        # Total Questions
        async with db.execute("SELECT COUNT(*) as total FROM questions") as cursor:
            stats["total_questions"] = (await cursor.fetchone())["total"]

        # NEET Questions
        async with db.execute("SELECT COUNT(*) as total FROM questions WHERE category = 'NEET'") as cursor:
            stats["neet_questions"] = (await cursor.fetchone())["total"]

        # MBBS Questions
        async with db.execute("SELECT COUNT(*) as total FROM questions WHERE category = 'MBBS'") as cursor:
            stats["mbbs_questions"] = (await cursor.fetchone())["total"]

        # Today's Posts (published today)
        async with db.execute(
            "SELECT COUNT(*) as total FROM questions WHERE status = 'published' AND DATE(created_at) = DATE('now')"
        ) as cursor:
            stats["today_posts"] = (await cursor.fetchone())["total"]

        # Total AI Generations
        async with db.execute("SELECT COUNT(*) as total FROM ai_usage") as cursor:
            stats["ai_generations"] = (await cursor.fetchone())["total"]

        # Failed Generations
        async with db.execute("SELECT COUNT(*) as total FROM ai_usage WHERE success = 0") as cursor:
            stats["failed_generations"] = (await cursor.fetchone())["total"]

        # Successful Posts
        async with db.execute("SELECT COUNT(*) as total FROM questions WHERE status = 'published'") as cursor:
            stats["successful_posts"] = (await cursor.fetchone())["total"]

        # Destinations Count
        async with db.execute("SELECT COUNT(*) as total FROM destinations WHERE enabled = 1") as cursor:
            stats["active_destinations"] = (await cursor.fetchone())["total"]

        # Active Schedules Count
        async with db.execute("SELECT COUNT(*) as total FROM schedules WHERE enabled = 1") as cursor:
            stats["active_schedules"] = (await cursor.fetchone())["total"]

    return stats
