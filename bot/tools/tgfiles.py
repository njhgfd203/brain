"""Скачивание файлов Telegram — совместимо с облачным и локальным Bot API.

В локальном режиме (self-hosted Bot API, TELEGRAM_LOCAL=1) сервер возвращает
абсолютный путь к файлу на общем томе — читаем его напрямую и удаляем, чтобы
не копить диск. В облачном режиме качаем по HTTP как обычно.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil

from aiogram import Bot

from bot.config import settings

logger = logging.getLogger(__name__)


async def fetch_to(bot: Bot, file_id: str, dst: str) -> None:
    """Кладёт файл Telegram в dst, работая в обоих режимах Bot API."""
    file = await bot.get_file(file_id)
    path = file.file_path
    if settings.local_bot_api and path and os.path.isabs(path) and os.path.exists(path):
        # Локальный сервер: файл уже на общем томе
        await asyncio.to_thread(shutil.copy, path, dst)
        try:
            os.remove(path)  # освобождаем диск Bot API сервера
        except OSError:
            logger.debug("Не удалось удалить исходник Bot API: %s", path)
    else:
        await bot.download_file(path, destination=dst)
