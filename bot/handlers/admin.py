"""Административные команды: /reindex, /stats."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from rag import indexer

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("reindex"))
async def cmd_reindex(message: Message) -> None:
    """Переиндексирует всю папку knowledge/."""
    await message.answer("Индексирую базу знаний...")
    try:
        summary = await asyncio.to_thread(indexer.reindex_all)
        text = (
            f"Реиндексация завершена.\n\n"
            f"Файлов обработано: {summary['files']}\n"
            f"Проиндексировано заново: {summary['indexed']}\n"
            f"Пропущено (без изменений): {summary['skipped']}\n"
            f"Пустых файлов: {summary['empty']}\n"
            f"Итого чанков в базе: {summary['chunks']}"
        )
        await message.answer(text)
    except Exception:
        logger.exception("Reindex failed")
        await message.answer("Ошибка при реиндексации. Подробности в логах.")
