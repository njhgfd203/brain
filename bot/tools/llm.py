"""Обёртка над OpenRouter/Claude через openai-совместимый клиент."""
from __future__ import annotations

import json
import logging

import openai

from bot.config import settings

logger = logging.getLogger(__name__)

_KNOWN_DOMAINS = ("technored", "ministry", "personal")

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


_EXTRACT_PROMPT = """\
Ты выделяешь конкретные задачи и договорённости из текста (заметки встречи, конспекта).

Найди поручения и дела «кто что должен сделать», дедлайны, следующие шаги.
Игнорируй общие рассуждения без действия.

Верни СТРОГО JSON-объект вида:
{"tasks": [{"text": "...", "domain": "...", "due_date": "YYYY-MM-DD или null"}]}

- text — кратко и в повелительном наклонении («подготовить материалы», «позвонить N»).
- domain — один из: technored, ministry, personal. Если не ясно — personal.
- due_date — ISO-дата, если в тексте есть срок; иначе null.
Если задач нет — верни {"tasks": []}. Никакого текста вне JSON."""


def _valid_date(value) -> str | None:
    """Возвращает ISO-дату 'YYYY-MM-DD' или None."""
    if not value or not isinstance(value, str):
        return None
    import re

    return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None


async def extract_tasks(text: str) -> list[dict]:
    """Выделяет задачи из текста через LLM. Возвращает список {text, domain, due_date}."""
    if not text or not text.strip():
        return []
    client = _get_client()
    try:
        resp = await client.chat.completions.create(
            model=settings.llm_model,
            max_tokens=1000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _EXTRACT_PROMPT},
                {"role": "user", "content": text[:12000]},
            ],
            extra_headers={"HTTP-Referer": "https://github.com/brain-bot", "X-Title": "brain"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception:
        logger.exception("extract_tasks failed")
        return []

    items = data.get("tasks", []) if isinstance(data, dict) else []
    result: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = (it.get("text") or "").strip()
        if not t:
            continue
        domain = it.get("domain", "personal")
        if domain not in _KNOWN_DOMAINS:
            domain = "personal"
        result.append({"text": t, "domain": domain, "due_date": _valid_date(it.get("due_date"))})
    return result


async def summarize_transcript(text: str) -> str:
    """Делает структурный конспект расшифровки (Markdown). Для длинных аудио (фаза H)."""
    client = _get_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": _SUMMARY_PROMPT},
            {"role": "user", "content": text[:60000]},
        ],
        extra_headers={"HTTP-Referer": "https://github.com/brain-bot", "X-Title": "brain"},
    )
    return resp.choices[0].message.content or ""


_SUMMARY_PROMPT = """\
Ты делаешь конспект расшифровки аудио (лекция, проповедь, встреча) для Даниила.

Сожми в структурный конспект на русском. Формат Markdown:

## Тема
одно-два предложения, о чём запись.

## Ключевые тезисы
- маркированный список главных мыслей (5–12 пунктов).

## Решения / выводы
- что решено или к чему пришли (если применимо).

## Задачи
- конкретные дела и договорённости (если есть; иначе «—»).

Пиши плотно, без воды. Не выдумывай того, чего нет в расшифровке."""


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
