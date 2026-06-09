FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# CPU-only torch: на VPS нет GPU, иначе pip тянет ~2.5 ГБ бесполезных CUDA-библиотек.
# Ставим torch заранее с CPU-индекса, чтобы sentence-transformers не подтянул CUDA-сборку.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
