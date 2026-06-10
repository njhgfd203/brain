"""Загрузка файлов знаний через бота: прислать .md → выбрать домен → сохранить + проиндексировать."""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.config import settings
from rag import indexer

logger = logging.getLogger(__name__)

router = Router()

_ALLOWED_EXT = (".md", ".markdown", ".txt")
_DOMAINS = ("technored", "ministry", "personal", "inbox")

_domain_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="technored", callback_data="updom:technored"),
            InlineKeyboardButton(text="ministry", callback_data="updom:ministry"),
        ],
        [
            InlineKeyboardButton(text="personal", callback_data="updom:personal"),
            InlineKeyboardButton(text="inbox", callback_data="updom:inbox"),
        ],
    ]
)


class UploadFlow(StatesGroup):
    choosing_domain = State()


def _safe_md_name(file_name: str) -> str:
    """Безопасное имя файла с расширением .md."""
    base = Path(file_name).name
    base = re.sub(r"[^\w.\-]+", "_", base).strip("_")
    stem = Path(base).stem or "upload"
    return f"{stem}.md"


@router.message(F.document)
async def on_document(message: Message, state: FSMContext) -> None:
    doc = message.document
    name = doc.file_name or "upload.md"
    if not name.lower().endswith(_ALLOWED_EXT):
        await message.answer("Пришли текстовый файл (.md, .markdown или .txt) — конспект или заметку.")
        return

    await state.set_state(UploadFlow.choosing_domain)
    await state.update_data(file_id=doc.file_id, file_name=name)
    await message.answer(
        f"📄 «{name}» — в какой раздел сохранить?",
        reply_markup=_domain_kb,
    )


@router.callback_query(F.data.startswith("updom:"))
async def on_domain_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    domain = callback.data.split(":", 1)[1]
    if domain not in _DOMAINS:
        await callback.answer("Неизвестный раздел")
        return

    data = await state.get_data()
    await state.clear()
    file_id = data.get("file_id")
    file_name = data.get("file_name")
    if not file_id:
        await callback.answer("Файл потерялся — пришли заново.")
        return

    await callback.answer("Загружаю…")

    dest_dir = Path(settings.knowledge_dir) / domain
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_md_name(file_name)
    dest = dest_dir / safe
    i = 1
    while dest.exists():
        dest = dest_dir / f"{Path(safe).stem}-{i}.md"
        i += 1

    try:
        file = await callback.bot.get_file(file_id)
        await callback.bot.download_file(file.file_path, destination=str(dest))
        result = await asyncio.to_thread(indexer.index_file, dest)
    except Exception:
        logger.exception("File upload/index failed for %s", file_name)
        if callback.message:
            await callback.message.edit_text(
                "Не удалось сохранить файл. Попробуй ещё раз."
            )
        return

    chunks = result.get("chunks", 0)
    if callback.message:
        await callback.message.edit_text(
            f"📄 Сохранено: {domain}/{dest.name} — чанков: {chunks}.\n"
            f"Теперь можно спрашивать через /ask."
        )
