"""Хендлеры /task, /today, /week — управление задачами через SQLite."""
from __future__ import annotations

import logging
import re
from datetime import date

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from db.database import add_task, get_today_tasks, get_week_tasks

logger = logging.getLogger(__name__)

router = Router()

def urgency_emoji(due_date: str | None) -> str:
    """Смайлик срочности по дате: 🔴 просрочено, 🟠 сегодня, 🟡 позже, ⚪ без срока."""
    if not due_date:
        return "⚪"
    today = date.today().isoformat()
    if due_date < today:
        return "🔴"
    if due_date == today:
        return "🟠"
    return "🟡"


# Допустимые домены
_DOMAINS = ("technored", "ministry", "personal")
_DOMAIN_PATTERN = re.compile(
    r"#(technored|ministry|personal)", re.IGNORECASE
)


def _parse_domain(text: str) -> tuple[str, str]:
    """Извлекает домен из #-тега, возвращает (домен, текст_без_тега)."""
    match = _DOMAIN_PATTERN.search(text)
    if match:
        domain = match.group(1).lower()
        cleaned = _DOMAIN_PATTERN.sub("", text)
        cleaned = re.sub(r"  +", " ", cleaned).strip()
        return domain, cleaned
    return "personal", text


def _parse_due(text: str) -> tuple[str | None, str]:
    """
    Ищет дату в тексте через dateparser.
    Возвращает (ISO-дата 'YYYY-MM-DD' | None, текст_без_даты).
    Берёт ПОСЛЕДНЕЕ найденное совпадение.
    """
    try:
        from dateparser.search import search_dates  # type: ignore[import]

        results = search_dates(
            text,
            languages=["ru"],
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
            },
        )
        if not results:
            return None, text

        # Берём последнее совпадение
        matched_str, parsed_dt = results[-1]
        iso_date = parsed_dt.strftime("%Y-%m-%d")

        # Убираем найденную подстроку из текста
        # Ищем последнее вхождение (на случай дублей)
        idx = text.rfind(matched_str)
        if idx != -1:
            cleaned = text[:idx] + text[idx + len(matched_str):]
        else:
            cleaned = text
        cleaned = re.sub(r"  +", " ", cleaned).strip()

        return iso_date, cleaned
    except Exception:
        logger.exception("dateparser failed on text: %r", text)
        return None, text


@router.message(Command("task"))
async def cmd_task(message: Message, command: CommandObject) -> None:
    args = command.args
    if not args or not args.strip():
        await message.answer(
            "Использование: /task <текст> [дата] [#домен]\n\n"
            "Примеры:\n"
            "• /task позвонить подрядчику завтра\n"
            "• /task #technored дедлайн по REDWELD в пятницу\n"
            "• /task купить подарок 2026-06-20\n"
            "• /task #ministry подготовить материалы для встречи\n\n"
            "Домены: #technored, #ministry, #personal (по умолчанию personal)"
        )
        return

    # 1. Извлекаем домен
    domain, remaining = _parse_domain(args.strip())

    # 2. Извлекаем дату из оставшегося текста
    due_date, task_text = _parse_due(remaining)

    task_text = task_text.strip()
    if not task_text:
        await message.answer(
            "Не удалось понять текст задачи. "
            "Напиши, пожалуйста, что именно нужно сделать.\n"
            "Например: /task позвонить подрядчику завтра"
        )
        return

    task_id = await add_task(task_text, domain, due_date)

    due_str = due_date if due_date else "без срока"
    await message.answer(
        f"Задача добавлена #{task_id}\n"
        f"Текст: {task_text}\n"
        f"Домен: {domain}\n"
        f"Срок: {due_str}"
    )


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    tasks = await get_today_tasks()
    if not tasks:
        await message.answer("На сегодня задач нет 🎉")
        return

    today_iso = date.today().isoformat()
    lines = ["Задачи на сегодня и просроченные:"]
    for t in tasks:
        overdue_mark = " ⚠️" if t["due_date"] < today_iso else ""
        lines.append(
            f"• [{t['id']}] {t['text']} ({t['domain']}) — {t['due_date']}{overdue_mark}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    tasks = await get_week_tasks()
    if not tasks:
        await message.answer("На неделю задач нет")
        return

    # Группируем по домену в Python
    groups: dict[str, list[dict]] = {}
    for t in tasks:
        domain = t["domain"]
        groups.setdefault(domain, []).append(t)

    # Порядок доменов: technored → ministry → personal → прочие
    ordered_domains = [d for d in ("technored", "ministry", "personal") if d in groups]
    for d in groups:
        if d not in ordered_domains:
            ordered_domains.append(d)

    lines = ["Задачи на ближайшие 7 дней:"]
    for domain in ordered_domains:
        lines.append(f"\n[{domain}]")
        for t in groups[domain]:
            lines.append(f"  • [{t['id']}] {t['text']} — {t['due_date']}")

    await message.answer("\n".join(lines))
