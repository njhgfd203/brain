"""Голосовые сообщения: транскрипция (Whisper) → классификация → роутинг.

Регистрируется ДО ask.router.
"""
from __future__ import annotations

import logging
import os

from aiogram import F, Router
from aiogram.types import Message

from bot.handlers.ask import _handle_question
from bot.handlers.meetings import add_meeting_and_reply
from bot.handlers.notes import save_note
from bot.handlers.tasks import create_task_from_text, format_task_added
from bot.tools.llm import classify_intent
from bot.tools.transcribe import temp_path, transcribe

logger = logging.getLogger(__name__)

router = Router()


async def _download_voice(message: Message) -> str:
    """Скачивает голосовое/аудио во временный файл, возвращает путь."""
    media = message.voice or message.audio
    file = await message.bot.get_file(media.file_id)
    dst = temp_path(".oga")
    await message.bot.download_file(file.file_path, destination=dst)
    return dst


@router.message(F.voice | F.audio)
async def handle_voice(message: Message) -> None:
    await message.bot.send_chat_action(message.chat.id, "typing")
    src = None
    try:
        src = await _download_voice(message)
        text = await transcribe(src)
    except Exception:
        logger.exception("Voice transcription failed")
        await message.answer("Не получилось распознать голосовое. Попробуй ещё раз.")
        return
    finally:
        if src and os.path.exists(src):
            try:
                os.remove(src)
            except OSError:
                pass

    if not text:
        await message.answer("Не разобрал голосовое — тишина или слишком тихо. Попробуй ещё раз.")
        return

    prefix = f"🎤 Распознал: «{text}»"
    intent = await classify_intent(text)

    if intent == "note":
        _, indexed = await save_note(text)
        reply = prefix + "\n\n📝 Сохранил как заметку"
        if not indexed:
            reply += " (индексация не удалась — /reindex)"
        await message.answer(reply)

    elif intent == "task":
        task = await create_task_from_text(text)
        if task is None:
            _, _ = await save_note(text)
            await message.answer(prefix + "\n\n📝 Не понял как задачу — сохранил заметкой")
        else:
            await message.answer(prefix + "\n\n" + format_task_added(task))

    elif intent == "meeting":
        await message.answer(prefix)
        await add_meeting_and_reply(message, text)

    else:  # question
        await message.answer(prefix + "\n\n💬 Отвечаю…")
        await _handle_question(message, text)
