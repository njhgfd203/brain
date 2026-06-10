FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# CPU-only torch: на VPS нет GPU, иначе pip тянет ~2.5 ГБ бесполезных CUDA-библиотек.
# Ставим torch заранее с CPU-индекса, чтобы sentence-transformers не подтянул CUDA-сборку.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# ffmpeg — конвертация голосовых Telegram (OGG/Opus) в mp3 для Whisper.
# После pip-слоёв, чтобы не инвалидировать кеш зависимостей.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python", "-m", "bot.main"]
