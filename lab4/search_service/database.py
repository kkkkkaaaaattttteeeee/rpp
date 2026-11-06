import os
from sqlalchemy import create_engine, text

# Драйвер psycopg2 для синхронной работы
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/flights_db")
engine = create_engine(DB_URL)

def get_flights_from_db(date_str: str):
    """Возвращает список рейсов из собственной БД за указанную дату."""
    with engine.connect() as connection:
        # Ищем рейсы, вылетающие в указанную дату
        query = text("""
            SELECT carrier, flight_number, origin, destination, departure_time, arrival_time, price 
            FROM flights 
            WHERE DATE(departure_time) = :date
        """)
        result = connection.execute(query, {"date": date_str})
        # Преобразуем строки БД в список словарей
        return [dict(row._mapping) for row in result]