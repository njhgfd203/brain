"""Планировщик фоновых задач: утренний дайджест, вечерняя сводка, напоминания о встречах."""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings
from bot.handlers.tasks import urgency_emoji
from db.database import get_today_tasks

logger = logging.getLogger(__name__)


def _parse_hm(value: str) -> tuple[int, int]:
    """'09:00' -> (9, 0). При ошибке — (9, 0)."""
    try:
        hh, mm = value.split(":")
        return int(hh), int(mm)
    except Exception:
        logger.warning("Не удалось разобрать время %r, использую 09:00", value)
        return 9, 0


async def send_morning_digest(bot: Bot) -> None:
    """Утром: задачи на сегодня и просроченные со смайликами срочности."""
    uid = settings.telegram_allowed_user_id
    tasks = await get_today_tasks()

    if not tasks:
        await bot.send_message(uid, "☀️ Доброе утро, Даниил!\n\nНа сегодня задач нет 🎉")
        return

    lines = ["☀️ Доброе утро, Даниил!", "", "Задачи на сегодня:"]
    for t in tasks:
        emoji = urgency_emoji(t["due_date"])
        lines.append(f"{emoji} [{t['id']}] {t['text']} ({t['domain']}) — {t['due_date']}")
    lines.append("\n🔴 просрочено · 🟠 сегодня")
    await bot.send_message(uid, "\n".join(lines))


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Создаёт и запускает планировщик с регулярными задачами."""
    scheduler = AsyncIOScheduler(timezone=settings.timezone)

    m_h, m_m = _parse_hm(settings.morning_time)
    scheduler.add_job(
        send_morning_digest,
        CronTrigger(hour=m_h, minute=m_m, timezone=settings.timezone),
        args=[bot],
        id="morning_digest",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Планировщик запущен (TZ=%s): утренний дайджест в %02d:%02d",
        settings.timezone, m_h, m_m,
    )
    return scheduler
