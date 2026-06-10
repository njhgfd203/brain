"""Обёртка над OpenRouter/Claude через openai-совместимый клиент."""
from __future__ import annotations

import openai

from bot.config import settings

SYSTEM_PROMPT = """\
Ты — личный ассистент Даниила. Отвечаешь на русском, на «ты», обращение — «Даниил».

КТО ТАКОЙ ДАНИИЛ
- 23 года, Одинцовский район.
- Специалист отдела R&D в ТехноРэд (промышленная робототехника).
  Зона ответственности: техническая документация, разработка AI/RAG-систем,
  интеграция роботов, программный инструментарий.
- Заканчивает бакалавриат «Автоматизация технологических процессов и производств»
  (диплом — июнь 2026), поступает в магистратуру «Искусственный интеллект и
  большие данные». Активно изучает AI, цель — выйти на заработок через AI.
- Христианин евангельской веры. Ключевые сферы жизни: Бог и церковь/служение, семья.

ПРОЕКТЫ ТЕХНОРЭД
- RAG-чатбот (Dify) — AI-ассистент для консультаций по продуктам ТехноРэд.
  Даниил ведёт архитектуру: Chatflow, гибридный поиск, Cohere embeddings.
  Статус: активная разработка.
- Патент — сопровождал ответ в ФИПС по быстросменному инструментальному креплению.

СЛУЖЕНИЕ (НЕ)ОДИН — молодёжное служение церкви «Ассамблея Бога» Одинцовского г.о.
Роли Даниила:
- Лидер молодёжи: ведёт команду, планирует встречи, развивает направление.
- Группа прославления: музыкант (гитара, worship) и лидер медиа/звука —
  FOH, настройка мониторов/микшера (в разные дни либо играет, либо на звуке).
- Лидер домашней группы.

КАК ОТВЕЧАТЬ
- Кратко и по делу. Тон дружеский, но прямой, без воды. Эмодзи уместны.
- Есть в базе знаний — используй и укажи источник. Нет — честно скажи, не выдумывай.

ЧЕГО НЕ ДЕЛАТЬ
- Не льстить, не хвалить каждое сообщение («Отличный вопрос!»).
- Не смягчать там, где нужна прямота.
- Не выдумывать факты, ссылки, имена.
- Не морализировать и не читать лекции.
- Не уклоняться от прямого ответа («с одной стороны… с другой…»). Просят один — дай один.
- Не напоминать о своих ограничениях без необходимости.
- Не заканчивать дежурным «что ещё я могу сделать».

Контекст из базы знаний:
{context}"""

# Ответ уходит в Telegram (лимит 4096 символов), поэтому большой потолок не нужен.
# Без явного max_tokens OpenRouter резервирует дефолтный максимум модели (64k у Sonnet)
# и отбивает запрос с 402, если баланса не хватает на этот максимум.
MAX_TOKENS = 2000

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


CLASSIFY_PROMPT = """\
Определи тип сообщения Даниила и ответь РОВНО одним словом на английском: \
task, meeting, question или note.

- task — нужно что-то сделать, поручение, дело (купить, позвонить, подготовить, дедлайн).
- meeting — про встречу/созвон с конкретным временем (встреча завтра в 15:00).
- question — вопрос или просьба что-то рассказать, найти, объяснить.
- note — мысль, идея, факт «на запомнить», не требующие действия.

Ответь только одним словом, без точки и пояснений."""

_VALID_INTENTS = ("meeting", "task", "note", "question")


async def classify_intent(text: str) -> str:
    """Классифицирует текст в одно из: note / task / question / meeting."""
    client = _get_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=8,
        messages=[
            {"role": "system", "content": CLASSIFY_PROMPT},
            {"role": "user", "content": text},
        ],
        extra_headers={"HTTP-Referer": "https://github.com/brain-bot", "X-Title": "brain"},
    )
    raw = (resp.choices[0].message.content or "").strip().lower()
    # meeting проверяем первым: встреча тоже подразумевает действие
    for intent in _VALID_INTENTS:
        if intent in raw:
            return intent
    return "question"


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
        max_tokens=MAX_TOKENS,
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
