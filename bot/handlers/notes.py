import asyncio
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.config import settings
from rag import indexer

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я личный ассистент Даниила.\n\n"
        "Доступные команды:\n"
        "/note <текст> — сохранить заметку в inbox\n"
        "/ask <вопрос> — спросить по базе знаний (или просто напиши текст)\n"
        "/reindex — переиндексировать базу знаний\n"
        "/task <текст> [дата] [#домен] — добавить задачу\n"
        "/today — задачи на сегодня и просроченные\n"
        "/week — обзор задач на 7 дней по доменам\n\n"
        "Появятся в следующих этапах:\n"
        "/search, /stats"
    )


@router.message(Command("note"))
async def cmd_note(message: Message, command: CommandObject) -> None:
    text = command.args
    if not text or not text.strip():
        await message.answer(
            "Использование: /note <текст>\n"
            "Например: /note Обсудить с командой новый дизайн"
        )
        return

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    time_str = today.strftime("%H:%M")

    inbox_dir = Path(settings.knowledge_dir) / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    note_file = inbox_dir / f"{date_str}.md"

    if not note_file.exists():
        frontmatter = (
            f"---\n"
            f"title: Inbox {date_str}\n"
            f"date: {date_str}\n"
            f"domain: inbox\n"
            f"tags: [inbox]\n"
            f"type: note\n"
            f"---\n"
        )
        note_file.write_text(frontmatter, encoding="utf-8")

    entry = f"\n## {time_str}\n\n{text.strip()}\n"
    with note_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    await message.answer(f"Сохранено в inbox/{date_str}.md")

    # Индексируем файл сразу после сохранения
    try:
        await asyncio.to_thread(indexer.index_file, note_file)
    except Exception:
        logger.exception("Failed to index note file %s", note_file)
        # Заметка уже сохранена на диске — только предупреждаем
        await message.answer("(Заметка сохранена, но индексация не удалась — попробуй /reindex)")
