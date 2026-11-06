from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import requests
import time
from datetime import datetime
import os

from database import get_flights_from_db
from logic import build_routes

app = FastAPI()

# Адреса поставщиков в Docker-сети
PROVIDERS = {
    1: "http://provider1:8000/flights",
    2: "http://provider2:8000/flights",
    3: "http://provider3:8000/flights"
}

@app.get("/health")
def health():
    """Проверка работоспособности самого сервиса поиска"""
    return {"status": "ok"}

@app.get("/search")
def search(
    origin: str = Query(...),
    destination: str = Query(...),
    date: str = Query(...)
):
    start_time = time.time()
    all_flights = []
    failed_providers = []

    # 1. Читаем из собственной БД
    try:
        db_flights = get_flights_from_db(date)
        all_flights.extend(db_flights)
    except Exception as e:
        print(f"Ошибка БД: {e}")

    # 2. Синхронный опрос поставщиков по очереди
    for p_id, url in PROVIDERS.items():
        p_start_time = time.time()
        success = False
        
        # Первая попытка
        try:
            # Ждем не более 1.8 секунды, чтобы оставить время на ретрай
            response = requests.get(url, params={"date": date}, timeout=1.8)
            if response.status_code == 200:
                all_flights.extend(response.json().get("flights", []))
                success = True
            elif response.status_code == 500:
                pass # Идем на ретрай
        except requests.exceptions.RequestException:
            pass # Идем на ретрай

        # Повторная попытка (если была ошибка или таймаут)
        if not success:
            # Проверяем, укладываемся ли мы в лимит 2 секунды на поставщика
            elapsed = time.time() - p_start_time
            if elapsed + 0.2 < 2.0:
                time.sleep(0.2) # Пауза перед повтором
                try:
                    # Таймаут на остаток времени
                    remaining_time = max(0.1, 2.0 - (time.time() - p_start_time))
                    response = requests.get(url, params={"date": date}, timeout=remaining_time)
                    if response.status_code == 200:
                        all_flights.extend(response.json().get("flights", []))
                        success = True
                except requests.exceptions.RequestException:
                    pass
            
        # Если после двух попыток успеха нет — поставщик в списке отвалившихся
        if not success:
            failed_providers.append(f"Provider {p_id}")

    # 3. Проверка на полное отсутствие данных
    if not all_flights and len(failed_providers) == len(PROVIDERS):
        raise HTTPException(status_code=503, detail="Поиск временно недоступен")

    # 4. Составление маршрутов
    routes = build_routes(all_flights, origin, destination)

    # 5. Формируем ответ
    processing_time = round((time.time() - start_time) * 1000, 2) # в миллисекундах
    
    return {
        "routes": routes,
        "failed_providers": failed_providers,
        "processing_time_ms": processing_time
    }