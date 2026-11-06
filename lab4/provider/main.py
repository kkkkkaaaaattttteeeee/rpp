import os
import random
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query

app = FastAPI()

# 1. Чтение параметров из переменных окружения (Таблица 1)
PROVIDER_ID = int(os.getenv("PROVIDER_ID", "1"))             # ID поставщика (1, 2 или 3)
BASE_DELAY_MS = int(os.getenv("BASE_DELAY_MS", "300"))       # Средняя задержка, мс
ERROR_RATE = float(os.getenv("ERROR_RATE", "0.05"))          # Вероятность ошибки 500 (5%)
LONG_DELAY_RATE = float(os.getenv("LONG_DELAY_RATE", "0.0")) # Вероятность задержки > 3с (10%)
FLIGHTS_COUNT = int(os.getenv("FLIGHTS_COUNT", "500"))       # Рейсов в сутки

# Список аэропортов для генерации (должен совпадать с БД)
AIRPORTS = [f"AP{i}" for i in range(1, 31)]

def generate_flights_for_date(date_str: str):
    """
    Генерирует 500 рейсов на указанную дату. 
    Использует детерминированный seed, чтобы для одной даты рейсы были одинаковыми.
    """
    # Фиксируем seed на основе даты и ID поставщика. 
    # Один и тот же запрос за ту же дату всегда даст те же рейсы.
    random.seed(f"{date_str}_{PROVIDER_ID}")
    
    flights = []
    # Парсим дату (ожидаем формат YYYY-MM-DD)
    base_date = datetime.strptime(date_str, "%Y-%m-%d")
    
    for _ in range(FLIGHTS_COUNT):
        origin, destination = random.sample(AIRPORTS, 2)
        
        # Случайное время вылета
        dep_hour = random.randint(0, 23)
        dep_minute = random.randint(0, 59)
        dep_time = base_date.replace(hour=dep_hour, minute=dep_minute)
        
        # Время в пути от 1 до 6 часов
        duration = random.randint(1, 6)
        arr_time = dep_time + timedelta(hours=duration)
        
        # Цена
        price = float(random.randint(30, 300) * 100)
        
        flights.append({
            "carrier": f"Provider{PROVIDER_ID}",
            "flight_number": f"P{PROVIDER_ID}{random.randint(100, 999)}",
            "origin": origin,
            "destination": destination,
            "departure_time": dep_time.isoformat(),
            "arrival_time": arr_time.isoformat(),
            "price": price
        })
    return flights

@app.get("/health")
async def health():
    """Проверка работоспособности заглушки"""
    return {"status": "ok", "provider_id": PROVIDER_ID}

@app.get("/flights")
async def get_flights(date: str = Query(..., description="Дата вылета в формате YYYY-MM-DD")):
    # 2. Симуляция задержки (с учетом ±30%)
    # random.uniform(0.7, 1.3) дает случайное число от 0.7 до 1.3
    jitter = random.uniform(0.7, 1.3)
    actual_delay_sec = (BASE_DELAY_MS * jitter) / 1000.0

    # 3. Симуляция долгой задержки (>3 секунд), если это Поставщик 3
    if random.random() < LONG_DELAY_RATE:
        actual_delay_sec = 3.0 + random.uniform(0.1, 1.0) # Задержка от 3.1 до 4.0 сек

    # Ждем рассчитанное время (имитация работы сети)
    await asyncio.sleep(actual_delay_sec)

    # 4. Симуляция ошибки 500
    if random.random() < ERROR_RATE:
        # Если выпал шанс на ошибку, прерываем выполнение и отдаем 500
        raise HTTPException(status_code=500, detail="Internal Server Error from Provider")

    # 5. Генерация и возврат рейсов
    flights = generate_flights_for_date(date)
    
    return {
        "provider_id": PROVIDER_ID,
        "date": date,
        "flights": flights
    }