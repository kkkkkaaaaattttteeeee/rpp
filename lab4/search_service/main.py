from fastapi import FastAPI, Query, HTTPException
from contextlib import asynccontextmanager
import httpx
import asyncio
import os
import time
from sqlalchemy.ext.asyncio import create_async_engine

from database import get_flights_from_db
from logic import build_routes

PROVIDERS = {
    1: "http://provider1:8000/flights",
    2: "http://provider2:8000/flights",
    3: "http://provider3:8000/flights"
}

# 1. Lifespan: создаем клиенты при старте, закрываем при выключении
@asynccontextmanager
async def lifespan(app: FastAPI):
    # При запуске
    app.state.http_client = httpx.AsyncClient()
    app.state.db_engine = create_async_engine(
        os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/flights_db"),
        pool_size=20,      # Увеличиваем пул
        max_overflow=10    # Добавляем резерв
    )
    yield
    # При остановке
    await app.state.http_client.aclose()
    await app.state.db_engine.dispose()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}

# 2. Функция опроса одного поставщика с тайм-аутом и ретраем
async def fetch_provider(client, p_id, url, date):
    start_time = time.time()
    for attempt in range(2):
        # Вычисляем оставшееся время до жесткого лимита в 2 секунды
        remaining = 2.0 - (time.time() - start_time)
        if remaining <= 0:
            break
            
        try:
            # 3. asyncio.timeout ограничивает время ожидания
            async with asyncio.timeout(remaining):
                response = await client.get(url, params={"date": date})
                if response.status_code == 200:
                    return response.json().get("flights", [])
                elif response.status_code == 500:
                    pass # Идем на ретрай
        except (httpx.RequestError, asyncio.TimeoutError):
            pass # Идем на ретрай

        if attempt == 0:
            # 4. Асинхронная пауза перед повтором
            await asyncio.sleep(0.2)
            
    return None # Если обе попытки провалились

@app.get("/search")
async def search(
    origin: str = Query(...),
    destination: str = Query(...),
    date: str = Query(...)
):
    start_time = time.time()
    client = app.state.http_client
    engine = app.state.db_engine

    # 5. Создаем задачи для БД и всех поставщиков
    db_task = get_flights_from_db(engine, date)
    provider_tasks = [
        fetch_provider(client, p_id, url, date) 
        for p_id, url in PROVIDERS.items()
    ]

    # 6. asyncio.gather: запускаем ВСЁ одновременно
    # return_exceptions=True гарантирует, что падение одной задачи не сломает остальные
    results = await asyncio.gather(db_task, *provider_tasks, return_exceptions=True)
    
    # Разбираем результаты
    db_flights = results[0] if not isinstance(results[0], Exception) else []
    provider_results = results[1:]

    all_flights = list(db_flights)
    failed_providers = []
    
    for idx, p_res in enumerate(provider_results, start=1):
        if p_res is None or isinstance(p_res, Exception):
            failed_providers.append(f"Provider {idx}")
        else:
            all_flights.extend(p_res)

    # Проверка на полный отказ
    if not all_flights and len(failed_providers) == 3:
        raise HTTPException(status_code=503, detail="Поиск временно недоступен")

    # Склейка маршрутов (чистая функция)
    routes = await asyncio.to_thread(build_routes, all_flights, origin, destination)
    processing_time = round((time.time() - start_time) * 1000, 2)

    return {
        "routes": routes,
        "failed_providers": failed_providers,
        "processing_time_ms": processing_time
    }