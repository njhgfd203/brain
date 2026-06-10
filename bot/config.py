from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram
    telegram_bot_token: str
    bot_mode: str = "polling"
    telegram_webhook_url: str = ""
    telegram_allowed_user_id: int

    # LLM
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "anthropic/claude-sonnet-4-5"

    # Paths
    knowledge_dir: str = "/app/knowledge"
    chroma_dir: str = "/app/chroma_db"
    sqlite_path: str = "/app/db/brain.sqlite"

    # RAG settings
    embedding_model: str = "intfloat/multilingual-e5-base"
    chunk_size: int = 400
    chunk_overlap: int = 50
    top_k_results: int = 5

    # Планировщик / напоминания
    timezone: str = "Europe/Moscow"
    morning_time: str = "09:00"          # утренний дайджест задач
    evening_time: str = "23:00"          # вечерняя сводка
    meeting_reminder_min: int = 60       # за сколько минут напоминать о встрече

    # Голос
    whisper_model: str = "openai/whisper-1"


settings = Settings()
