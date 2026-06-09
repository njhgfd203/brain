"""Обёртка над OpenRouter/Claude через openai-совместимый клиент."""
from __future__ import annotations

import openai

from bot.config import settings

SYSTEM_PROMPT = """\
Ты личный ассистент Даниила. У тебя есть доступ к его базе знаний.

Отвечай на русском языке. Будь конкретным и кратким.
Если информация есть в базе знаний — используй её и укажи источник.
Если информации нет — честно скажи об этом, не придумывай.

Контекст из базы знаний:
{context}"""

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


async def ask_llm(question: str, chunks: list[dict]) -> str:
    """Отправляет вопрос в LLM с контекстом из RAG-чанков."""
    if chunks:
        context_parts = [
            f"[источник: {c['source_file']}]\n{c['text']}"
            for c in chunks
        ]
        context = "\n\n".join(context_parts)
    else:
        context = "(база знаний пуста или ничего не найдено)"

    client = _get_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
            {"role": "user", "content": question},
        ],
        extra_headers={
            "HTTP-Referer": "https://github.com/brain-bot",
            "X-Title": "brain",
        },
    )
    return resp.choices[0].message.content or ""
