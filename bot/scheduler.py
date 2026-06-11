"""Планировщик фоновых задач: утренний дайджест, вечерняя сводка, напоминания о встречах."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from bot.config import settings
from bot.handlers.tasks import build_evening_view, urgency_emoji
from db.database import get_due_meetings, get_today_tasks, mark_meeting_reminded

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
        lines.append(f"{emoji} {t['text']} ({t['domain']})")
    lines.append("\n🔴 просрочено · 🟢 сегодня")
    await bot.send_message(uid, "\n".join(lines))


async def send_evening_review(bot: Bot) -> None:
    """Вечером: список незакрытых задач с кнопками ✅ и переносом на завтра."""
    uid = settings.telegram_allowed_user_id
    text, markup = await build_evening_view()
    await bot.send_message(uid, text, reply_markup=markup)


async def check_meeting_reminders(bot: Bot) -> None:
    """Каждую минуту: напоминает о встречах, до которых <= окна напоминания."""
    uid = settings.telegram_allowed_user_id
    now = datetime.now()
    now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
    limit_iso = (now + timedelta(minutes=settings.meeting_reminder_min)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    for m in await get_due_meetings(now_iso, limit_iso):
        try:
            when = datetime.strptime(m["start_at"], "%Y-%m-%d %H:%M:%S").strftime("%H:%M")
        except Exception:
            when = m["start_at"]
        await bot.send_message(uid, f"🔔 Через час встреча: {m['title']} — в {when}")
        await mark_meeting_reminded(m["id"])


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

    e_h, e_m = _parse_hm(settings.evening_time)
    scheduler.add_job(
        send_evening_review,
        CronTrigger(hour=e_h, minute=e_m, timezone=settings.timezone),
        args=[bot],
        id="evening_review",
        replace_existing=True,
    )

    scheduler.add_job(
        check_meeting_reminders,
        IntervalTrigger(minutes=1),
        args=[bot],
        id="meeting_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Планировщик запущен (TZ=%s): утро %02d:%02d, вечер %02d:%02d, "
        "напоминания о встречах за %d мин",
        settings.timezone, m_h, m_m, e_h, e_m, settings.meeting_reminder_min,
    )
    return scheduler
