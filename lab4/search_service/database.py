import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Драйвер asyncpg для асинхронной работы
DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/flights_db")

async def get_flights_from_db(engine, date_str: str):
    """Асинхронно возвращает рейсы из БД."""
    async with engine.connect() as connection:
        query = text("""
            SELECT carrier, flight_number, origin, destination, departure_time, arrival_time, price 
            FROM flights 
            WHERE DATE(departure_time) = :date
        """)
        result = await connection.execute(query, {"date": date_str})
        return [dict(row._mapping) for row in result]