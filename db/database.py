"""Async CRUD-слой для SQLite через aiosqlite."""
from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from bot.config import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.sqlite_path

# Путь к схеме относительно этого файла
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    """Создаёт папку и таблицы (идемпотентно)."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(schema)
        await db.commit()
    logger.info("Database initialised at %s", DB_PATH)


async def add_task(
    text: str,
    domain: str = "personal",
    due_date: str | None = None,
) -> int:
    """Вставляет задачу, возвращает id новой строки."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tasks (text, domain, due_date) VALUES (?, ?, ?)",
            (text, domain, due_date),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_today_tasks() -> list[dict]:
    """Незавершённые задачи на сегодня и просроченные."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, text, domain, due_date
            FROM tasks
            WHERE is_done = 0
              AND due_date IS NOT NULL
              AND due_date <= date('now', 'localtime')
            ORDER BY due_date ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_week_tasks() -> list[dict]:
    """Незавершённые задачи на ближайшие 7 дней (включая сегодня)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, text, domain, due_date
            FROM tasks
            WHERE is_done = 0
              AND due_date IS NOT NULL
              AND due_date >= date('now', 'localtime')
              AND due_date <= date('now', 'localtime', '+7 days')
            ORDER BY domain ASC, due_date ASC
            """
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def complete_task(task_id: int) -> bool:
    """Помечает задачу выполненной. Возвращает True если строка была обновлена."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE tasks
            SET is_done = 1, completed_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_done = 0
            """,
            (task_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
