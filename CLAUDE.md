# CLAUDE.md — Personal Brain (Личная база знаний)

> Этот файл — главный контекст проекта для Claude Code.
> Читай его перед любым изменением кода или структуры.

---

## 📍 Статус и как продолжить (читай первым)

**Состояние на 2026-06-09:** Этапы **1, 2, 3 реализованы** (код готов, прошёл ревью и `py_compile`), но **ни разу не запускались** — зависимости локально не ставились, деплой только на VPS.

**Следующий шаг:** перенести проект на VPS → заполнить `.env` → запустить (`BOT_MODE=polling`) → прогнать смоук-тест → починить найденное → делать **Этап 4**.

**Подробный handoff** (карта файлов, что проверено, смоук-тест, архитектурные решения, известные ограничения, бэклог Этапа 4): см. [`HANDOFF.md`](./HANDOFF.md).
**Инструкция по запуску и секретам:** см. [`README.md`](./README.md).

**Рабочая схема разработки:** Opus — архитектор + ревьюер (план/фазы, потом ревью/тесты/шлифовка). Sonnet — пишет код по плану (суб-агент `coder` в `.claude/agents/coder.md`). Архитектурные решения кодеру не делегируются.

---

## Что это за проект

Личный AI-ассистент Даниила, доступный через Telegram 24/7.
Хранит всё: заметки, планы, задачи, конспекты встреч.
Отвечает с контекстом — знает о проектах ТехноРэда, служении (НЕ)ОДИН, личных делах.

**Принципы:**
- Все данные только на своём VPS (self-hosted)
- Никаких SaaS-платформ (не Dify, не Notion AI)
- Простота важнее функциональности — лучше меньше, но стабильно
- Код пишется так, чтобы легко расширять

---

## Стек

| Слой | Технология | Зачем |
|------|-----------|-------|
| Бот | aiogram 3 | Telegram-интерфейс, webhook (VPS) / polling (отладка) |
| LLM | Claude API через OpenRouter | Умные ответы, понимание контекста |
| RAG | ChromaDB (встроенная) + sentence-transformers | Семантический поиск по заметкам |
| Заметки | Markdown-файлы | Источник знаний, читаемо вручную |
| Задачи | SQLite (aiosqlite) | Дедлайны, напоминания |
| Деплой | Docker Compose | Одна команда — всё работает |

**Модель:** `anthropic/claude-sonnet-4-5` через OpenRouter  
**Embeddings:** `intfloat/multilingual-e5-base` (контекст 512 токенов, хорошо работает по-русски)

> ⚠️ e5 требует префиксов: запросы индексируются как `passage: ...`, поисковые
> запросы — как `query: ...`. Без этого качество поиска падает.
> ChromaDB — **встроенная** (`PersistentClient`), без отдельного контейнера.

---

## Структура проекта

```
brain/
├── CLAUDE.md                  ← этот файл
├── docker-compose.yml
├── .env                       ← секреты (не в git)
├── .env.example
│
├── bot/                       ← Telegram-бот
│   ├── main.py                ← точка входа, webhook/polling (BOT_MODE)
│   ├── config.py              ← настройки из .env
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── notes.py           ← /note, /search
│   │   ├── tasks.py           ← /task, /today, /week
│   │   ├── ask.py             ← /ask (RAG + LLM)
│   │   └── admin.py           ← /reindex, /stats
│   └── tools/
│       ├── __init__.py
│       ├── llm.py             ← обёртка над OpenRouter/Claude
│       └── formatter.py       ← форматирование ответов для TG
│
├── rag/
│   ├── indexer.py             ← md-файлы → embeddings → ChromaDB
│   ├── retriever.py           ← семантический поиск, возврат чанков
│   └── watcher.py             ← watchdog: авто-реиндекс при изменении файла
│
├── db/
│   ├── schema.sql             ← DDL для SQLite
│   ├── database.py            ← async CRUD через aiosqlite
│   └── brain.sqlite           ← файл БД (не в git)
│
└── knowledge/                 ← ТВОИ ЗАМЕТКИ (главное)
    ├── _templates/            ← шаблоны для новых заметок
    │   ├── meeting.md
    │   ├── project.md
    │   └── brainstorm.md
    ├── technored/             ← работа, проекты ТехноРэда
    ├── ministry/              ← служение (НЕ)ОДИН
    ├── personal/              ← личное, цели, рефлексия
    └── inbox/                 ← быстрые заметки из бота (не разобранные)
```

---

## Переменные окружения (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=
BOT_MODE=webhook                              # webhook (VPS) | polling (отладка)
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhook
TELEGRAM_ALLOWED_USER_ID=   # твой Telegram user_id — только ты

# LLM
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-sonnet-4-5

# Пути
KNOWLEDGE_DIR=/app/knowledge
CHROMA_DIR=/app/chroma_db
SQLITE_PATH=/app/db/brain.sqlite

# Настройки RAG
EMBEDDING_MODEL=intfloat/multilingual-e5-base
CHUNK_SIZE=400
CHUNK_OVERLAP=50
TOP_K_RESULTS=5
```

---

## Команды бота

| Команда | Что делает |
|---------|-----------|
| `/note <текст>` | Сохраняет заметку в `knowledge/inbox/YYYY-MM-DD.md` и индексирует |
| `/ask <вопрос>` | RAG-поиск по базе знаний + ответ от LLM |
| `/task <текст> [дата]` | Добавляет задачу. Дата: "завтра", "пт", "2025-06-15" |
| `/today` | Задачи на сегодня + просроченные |
| `/week` | Обзор задач на 7 дней по доменам |
| `/search <запрос>` | Семантический поиск, возвращает топ-5 чанков с источником |
| `/reindex` | Переиндексировать всю папку knowledge/ |
| `/stats` | Количество заметок, задач, последний индекс |

**Свободный текст** (без команды) → обрабатывается как `/ask`

---

## Система заметок (knowledge/)

### Домены
- `technored/` — проекты REDWELD, REDLOAD, RAG-чатбот, документация
- `ministry/` — (НЕ)ОДИН: встречи, планы, команда, контент
- `personal/` — цели, рефлексия, идеи, обучение
- `inbox/` — необработанные заметки из бота

### Формат файла (frontmatter)

```markdown
---
title: Название заметки
date: 2025-06-09
domain: technored | ministry | personal
tags: [rag, chatbot, dify]
type: note | meeting | project | brainstorm | task
---

Содержимое заметки...
```

### Шаблон встречи (`_templates/meeting.md`)

```markdown
---
title: Встреча — {{тема}}
date: {{дата}}
domain: {{домен}}
tags: [meeting]
type: meeting
participants: []
---

## Повестка


## Решения и договорённости


## Задачи по итогам
- [ ] 

## Следующая встреча

```

### Шаблон мозгового штурма (`_templates/brainstorm.md`)

```markdown
---
title: Брейншторм — {{тема}}
date: {{дата}}
domain: {{домен}}
tags: [brainstorm]
type: brainstorm
---

## Вопрос / задача


## Идеи (без фильтра)


## Топ-3 идеи


## Следующий шаг

```

---

## Архитектура RAG

```
knowledge/*.md
      ↓ indexer.py
  парсинг frontmatter
  проверка hash файла (пропуск неизменённых — инкрементальный реиндекс)
  разбивка на чанки (400 токенов, overlap 50)
  добавление метаданных (domain, date, source_file)
      ↓
  e5: "passage: {чанк}" → embeddings
      ↓
  ChromaDB (collection: "brain", встроенный PersistentClient)
      ↓ retriever.py
  "query: {вопрос}" → embedding
  cosine similarity → топ-5 чанков
      ↓ llm.py
  system prompt + чанки + вопрос → Claude
      ↓
  ответ пользователю
```

### System prompt для LLM

```
Ты личный ассистент Даниила. У тебя есть доступ к его базе знаний.

Отвечай на русском языке. Будь конкретным и кратким.
Если информация есть в базе знаний — используй её и укажи источник.
Если информации нет — честно скажи об этом, не придумывай.

Контекст из базы знаний:
{context}
```

---

## SQLite схема

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    domain TEXT DEFAULT 'personal',  -- technored | ministry | personal
    due_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    is_done BOOLEAN DEFAULT 0
);

CREATE TABLE notes_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    content_hash TEXT,               -- hash содержимого (см. примечание ниже)
    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    chunk_count INTEGER
);
```

> **Примечание (с Этапа 2):** инкрементальный реиндекс реализован через
> `file_hash` в **метаданных чанков ChromaDB**, а не через `notes_index`.
> Таблица `notes_index` — для `/stats` (Этап 3): счётчики/время индекса.

---

## Docker Compose

```yaml
version: "3.9"

services:
  bot:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./knowledge:/app/knowledge
      - ./db:/app/db
      - chroma_data:/app/chroma_db          # встроенная ChromaDB (PersistentClient)
    ports:
      - "8443:8443"

volumes:
  chroma_data:
```

> ChromaDB работает **внутри** контейнера бота (PersistentClient по пути
> `CHROMA_DIR`), отдельного сервиса нет. Данные переживают перезапуск
> благодаря volume `chroma_data`.

---

## Порядок разработки

### Этап 1 — Скелет + заметки (делай первым)
- [x] Инициализация проекта, `requirements.txt`
- [x] `bot/main.py` — webhook/polling (BOT_MODE), старт
- [x] `bot/handlers/notes.py` — команда `/note`, сохранение в inbox/
- [x] `bot/config.py` — загрузка `.env` (pydantic-settings)
- [x] `bot/middlewares/access.py` — фильтр по `TELEGRAM_ALLOWED_USER_ID`
- [x] `Dockerfile` + `docker-compose.yml` — базовая конфигурация
- [ ] Проверка: бот принимает `/note текст` и сохраняет файл (нужен запуск с реальным токеном)

### Этап 2 — RAG-ядро (главная ценность)
- [x] `rag/embedder.py` — модель e5, e5-префиксы query/passage
- [x] `rag/indexer.py` — парсинг md, токен-чанкинг, запись в ChromaDB, инкрементально по hash (hash в метаданных чанков)
- [x] `rag/retriever.py` — поиск по запросу
- [x] `bot/tools/llm.py` — обёртка OpenRouter
- [x] `bot/handlers/ask.py` — команда `/ask` + свободный текст
- [x] `bot/handlers/admin.py` — команда `/reindex`
- [x] Хук: `/note` индексирует файл сразу после сохранения
- [ ] Проверка: `/ask` отвечает с реальным контекстом из заметок (нужен запуск с токеном и ключом OpenRouter)

### Этап 3 — Задачи и дашборд
- [x] `db/schema.sql` + `db/database.py` (aiosqlite, init_db при старте)
- [x] `bot/handlers/tasks.py` — `/task`, `/today`, `/week` (+ `#домен`-тег)
- [x] Парсинг дат на русском через `dateparser` ("завтра", "в пятницу", ISO)
- [x] `init_db()` вызывается в обоих режимах (polling/webhook)
- [ ] Проверка: задачи создаются, `/today` показывает список (нужен запуск с токеном)

### Этап 4 — Качество жизни (потом)
- [ ] `rag/watcher.py` — авто-реиндекс при изменении файлов
- [ ] Голосовые сообщения → Whisper → текст → `/note`
- [ ] Inline-кнопки для задач (✅ отметить выполненной)
- [ ] `/search` с отображением источника и домена
- [ ] Еженедельный дайджест (cron)

---

## Важные решения (не менять без причины)

| Решение | Почему |
|---------|--------|
| Markdown-файлы как источник | Читаемо без бота, легко бэкапить гитом, можно редактировать в Obsidian |
| ChromaDB встроенная, не отдельный сервис | Один пользователь, минус контейнер и сетевой слой, бэкап = папка |
| e5-base, не MiniLM | У MiniLM контекст всего 128 токенов — чанк 400 обрезался бы. У e5 контекст 512 |
| OpenRouter, не прямой Anthropic API | Гибкость смены модели, работает из РФ |
| aiogram 3, не python-telegram-bot | Async нативно, уже есть опыт |
| SQLite для задач | Не нужна сетевая БД для одного пользователя |
| Webhook на VPS, polling для отладки (BOT_MODE) | Webhook надёжнее в проде; polling не требует HTTPS-тоннеля локально |

---

## Что НЕ делаем (намеренно)

- Никакого веб-интерфейса — только Telegram
- Никакого Dify, LangFlow, n8n — чистый Python
- Никаких облачных БД — всё локально на VPS
- Никакой авторизации — бот только для одного user_id

---

## Начало работы на VPS

```bash
git clone <repo> brain && cd brain
cp .env.example .env
# заполни .env
docker compose up -d
# установить webhook:
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WEBHOOK_URL>"
```
