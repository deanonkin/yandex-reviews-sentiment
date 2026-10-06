# Dockerfile
FROM python:3.11-slim

# Системные пакеты для Playwright + свежих колёс ML-библиотек
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget curl ca-certificates gnupg \
        build-essential gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала requirements — кэш слоёв при пересборке
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Playwright-браузер + системные зависимости
RUN playwright install --with-deps chromium

# Код
COPY *.py ./

# Модели будут качаться в HF_HOME при первом запуске
ENV HF_HOME=/hf-cache
ENV PYTHONUNBUFFERED=1

CMD ["python", "pipeline.py"]