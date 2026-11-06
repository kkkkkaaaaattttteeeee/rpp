# Берем легкий образ Python
FROM python:3.11-slim

# Создаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

RUN apt-get update && apt-get install -y curl
# Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь наш код (main.py) в контейнер
COPY . .

# Команда для запуска сервера. 
# Важно: хост 0.0.0.0, чтобы сервер был доступен снаружи контейнера
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]