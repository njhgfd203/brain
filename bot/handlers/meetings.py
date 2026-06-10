"""Хендлеры /meet, /meetings — встречи с напоминанием за час."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.handlers.tasks import _parse_domain
from db.database import add_meeting, get_upcoming_meetings

logger = logging.getLogger(__name__)

router = Router()

_WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _format_dt(start_at: str) -> str:
    """'2026-06-11 15:00:00' -> 'Чт 11.06 15:00'."""
    try:
        dt = datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S")
        return f"{_WEEKDAYS_RU[dt.weekday()]} {dt.strftime('%d.%m %H:%M')}"
    except Exception:
        return start_at


def create_meeting_from_text(raw: str) -> dict | None:
    """Парсит '#домен текст когда' → создаёт встречу. None, если дату/время не нашли."""
    domain, remaining = _parse_domain(raw.strip())
    try:
        from dateparser.search import search_dates  # type: ignore[import]

        results = search_dates(
            remaining,
            languages=["ru"],
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
    except Exception:
        logger.exception("dateparser failed on meeting text: %r", remaining)
        results = None

    if not results:
        return None

    matched_str, parsed_dt = results[-1]
    start_at = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")

    idx = remaining.rfind(matched_str)
    title = remaining[:idx] + remaining[idx + len(matched_str):] if idx != -1 else remaining
    title = re.sub(r"  +", " ", title).strip(" -—,")
    if not title:
        title = "встреча"

    return {"domain": domain, "title": title, "start_at": start_at, "dt": parsed_dt}


async def add_meeting_and_reply(message: Message, raw: str) -> None:
    """Создаёт встречу из текста и отвечает подтверждением (общий код для /meet и FSM)."""
    parsed = create_meeting_from_text(raw)
    if parsed is None:
        await message.answer(
            "Не понял, когда встреча. Укажи дату и время.\n"
            "Например: «Встреча по REDWELD завтра в 15:00»"
        )
        return

    mid = await add_meeting(parsed["title"], parsed["domain"], parsed["start_at"])
    await message.answer(
        f"🤝 Встреча #{mid} добавлена\n"
        f"Тема: {parsed['title']}\n"
        f"Когда: {_format_dt(parsed['start_at'])}\n"
        f"Домен: {parsed['domain']}\n\n"
        f"Напомню за час."
    )


@router.message(Command("meet"))
async def cmd_meet(message: Message, command: CommandObject) -> None:
    args = command.args
    if not args or not args.strip():
        await message.answer(
            "Использование: /meet <тема> <когда> [#домен]\n\n"
            "Примеры:\n"
            "• /meet встреча по REDWELD завтра в 15:00\n"
            "• /meet #ministry разбор воскресной встречи в пятницу в 19:30"
        )
        return
    await add_meeting_and_reply(message, args.strip())


@router.message(Command("meetings"))
async def cmd_meetings(message: Message) -> None:
    meetings = await get_upcoming_meetings()
    if not meetings:
        await message.answer("Ближайших встреч нет.")
        return
    lines = ["🗓 Ближайшие встречи:"]
    for m in meetings:
        lines.append(f"• [{m['id']}] {_format_dt(m['start_at'])} — {m['title']} ({m['domain']})")
    await message.answer("\n".join(lines))
