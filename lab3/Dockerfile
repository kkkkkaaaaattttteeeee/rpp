# Сборка
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Образ
FROM python:3.11-slim
WORKDIR /app

# Создаем непривилегированного пользователя
RUN useradd -m appuser

# Копируем зависимости из билдера
COPY --from=builder /install /usr/local

# Копируем код
COPY . .

# Даем права пользователю на папку
RUN chown -R appuser:appuser /app
USER appuser

# Переменные окружения по умолчанию
ENV PORT=5000
ENV LOG_LEVEL=INFO
ENV PYTHONPATH=/app

EXPOSE 5000

# Запуск Gunicorn с ОДНИМ воркером
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "web.app:app"]