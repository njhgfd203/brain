"""Транскрипция голосовых через OpenRouter (Whisper). Конвертация OGG→mp3 через ffmpeg."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile

import openai

from bot.config import settings

logger = logging.getLogger(__name__)

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


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
        client = _get_client()
        with open(mp3_path, "rb") as f:
            resp = await client.audio.transcriptions.create(
                model=settings.whisper_model,
                file=f,
            )
        return (resp.text or "").strip()
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
