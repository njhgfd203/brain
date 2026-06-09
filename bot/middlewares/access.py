from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.config import settings


class AccessMiddleware(BaseMiddleware):
    """Пропускает апдейты только от одного разрешённого пользователя.

    Зарегистрирован на уровне update, поэтому `event` — это `Update`.
    Пользователя берём из `data["event_from_user"]`, который aiogram
    заполняет для любого типа апдейта (message, callback_query, inline и т.д.).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")

        # Не можем определить пользователя или это не он — тихо игнорируем
        if user is None or user.id != settings.telegram_allowed_user_id:
            return None

        return await handler(event, data)
