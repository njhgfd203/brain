"""Транскрипция голосовых/аудио через OpenRouter (Whisper). Конвертация в mp3 через ffmpeg.

OpenRouter-эндпоинт /audio/transcriptions принимает JSON с base64-аудио
(input_audio: {data, format}), а НЕ multipart — поэтому шлём напрямую через httpx.

Короткие сообщения — transcribe(). Длинные записи (лекции/проповеди) — transcribe_long(),
которая режет аудио на сегменты (Whisper-запрос ограничен ~25 МБ) и склеивает текст.
"""
from __future__ import annotations

import asyncio
import base64
import glob
import logging
import os
import shutil
import tempfile
from typing import Awaitable, Callable

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


async def _send_whisper(mp3_path: str) -> str:
    """Отправляет один mp3 в Whisper (OpenRouter) и возвращает распознанный текст."""
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
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    text = data.get("text")
    if text is None:
        logger.error("Unexpected transcription response shape: %s", list(data.keys()))
        return ""
    return text.strip()


async def transcribe(src_path: str) -> str:
    """Распознаёт короткое голосовое: конвертация в mp3 → один Whisper-запрос."""
    mp3_path = await _to_mp3(src_path)
    try:
        return await _send_whisper(mp3_path)
    finally:
        try:
            os.remove(mp3_path)
        except OSError:
            pass


ProgressCb = Callable[[int, int], Awaitable[None]]


async def transcribe_long(src_path: str, progress_cb: ProgressCb | None = None) -> str:
    """Распознаёт длинную запись: режет на сегменты по whisper_chunk_sec и склеивает текст.

    progress_cb(done, total) — необязательный async-колбэк прогресса между чанками.
    """
    workdir = tempfile.mkdtemp(prefix="whisper_")
    pattern = os.path.join(workdir, "chunk_%03d.mp3")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", src_path,
        "-ar", "16000", "-ac", "1",
        "-f", "segment", "-segment_time", str(settings.whisper_chunk_sec),
        pattern,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        shutil.rmtree(workdir, ignore_errors=True)
        raise RuntimeError(f"ffmpeg segment failed: {stderr.decode(errors='ignore')[-500:]}")

    chunks = sorted(glob.glob(os.path.join(workdir, "chunk_*.mp3")))
    try:
        texts: list[str] = []
        total = len(chunks)
        for i, ch in enumerate(chunks):
            if progress_cb:
                await progress_cb(i, total)
            texts.append(await _send_whisper(ch))
        if progress_cb:
            await progress_cb(total, total)
        return " ".join(t for t in texts if t).strip()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def temp_path(suffix: str = ".oga") -> str:
    """Уникальный путь во временной папке (файл не создаётся)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path
