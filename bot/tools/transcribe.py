"""Транскрипция голосовых через OpenRouter (Whisper). Конвертация OGG→mp3 через ffmpeg.

OpenRouter-эндпоинт /audio/transcriptions принимает JSON с base64-аудио
(input_audio: {data, format}), а НЕ multipart — поэтому шлём напрямую через httpx.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


async def _to_mp3(src_path: str) -> str:
    """Конвертирует аудио в mono 16kHz mp3 через ffmpeg. Возвращает путь к mp3."""
    dst_path = src_path + ".mp3"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1", dst_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode(errors='ignore')[-500:]}")
    return dst_path


async def transcribe(src_path: str) -> str:
    """Конвертирует голосовой файл и распознаёт речь через Whisper (OpenRouter)."""
    mp3_path = await _to_mp3(src_path)
    try:
        with open(mp3_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        url = settings.openrouter_base_url.rstrip("/") + "/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.whisper_model,
            "input_audio": {"data": b64, "format": "mp3"},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        text = data.get("text")
        if text is None:
            logger.error("Unexpected transcription response shape: %s", list(data.keys()))
            text = ""
        return text.strip()
    finally:
        try:
            os.remove(mp3_path)
        except OSError:
            pass


def temp_path(suffix: str = ".oga") -> str:
    """Уникальный путь во временной папке (файл не создаётся)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path
