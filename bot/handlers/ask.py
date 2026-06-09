"""Хендлеры /ask и свободного текста — RAG + LLM."""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.tools.llm import ask_llm
from rag import retriever

logger = logging.getLogger(__name__)

router = Router()


async def _handle_question(message: Message, question: str) -> None:
    """Общая логика: поиск в RAG → LLM → ответ пользователю."""
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")

        chunks = await asyncio.to_thread(retriever.search, question)
        answer = await ask_llm(question, chunks)

        if chunks:
            unique_sources = list(dict.fromkeys(c["source_file"] for c in chunks))
            sources_block = "\n\nИсточники:\n" + "\n".join(
                f"• {s}" for s in unique_sources
            )
            reply = answer + sources_block
        else:
            reply = answer

        # Без parse_mode: ответ LLM — произвольный текст, HTML/Markdown-разметка
        # могла бы ломать парсинг сущностей Telegram (ошибка 400).
        await message.answer(reply)
    except Exception:
        logger.exception("Error handling question: %r", question)
        await message.answer(
            "Произошла ошибка при обработке вопроса. Попробуй ещё раз."
        )


@router.message(Command("ask"))
async def cmd_ask(message: Message, command: CommandObject) -> None:
    question = command.args
    if not question or not question.strip():
        await message.answer(
            "Использование: /ask <вопрос>\n"
            "Например: /ask Что обсуждали на встрече по REDWELD?"
        )
        return
    await _handle_question(message, question.strip())


@router.message(F.text & ~F.text.startswith("/"))
async def free_text_handler(message: Message) -> None:
    """Свободный текст без команды — обрабатывается как /ask."""
    question = (message.text or "").strip()
    if not question:
        return
    await _handle_question(message, question)
