import os
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, Float, Index

# 1. Настройки подключения к базе данных
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/flights_db")
engine = create_engine(DB_URL)

# 2. Определение структуры таблицы
metadata = MetaData()

flights_table = Table(
    'flights', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('carrier', String(50), nullable=False),
    Column('flight_number', String(20), nullable=False),
    Column('origin', String(10), nullable=False),
    Column('destination', String(10), nullable=False),
    Column('departure_time', DateTime, nullable=False),
    Column('arrival_time', DateTime, nullable=False),
    Column('price', Float, nullable=False)
)

# Создаем индекс для быстрого поиска по дате вылета (требование задачи)
idx_departure = Index('idx_departure_time', flights_table.c.departure_time)

# 3. Списки для генерации
AIRPORTS = [f"AP{i}" for i in range(1, 31)]  # 30 аэропортов (AP1...AP30)
CARRIERS = ["CarrierA", "CarrierB", "CarrierC", "CarrierD", "CarrierE"]
START_DATE = datetime(2026, 8, 1)  # Дата начала расписания
DAYS_COUNT = 120                   # На 120 дней
FLIGHTS_PER_DAY = 1500             # 1500 рейсов в сутки

def generate_and_load_data():
    # Фиксируем seed для детерминированности (при повторном запуске рейсы будут те же)
    random.seed(42)
    
    # Создаем таблицу в БД, если ее еще нет
    print("Создание таблицы...")
    metadata.create_all(engine)
    
    flights_data = []
    
    # Генерируем данные
    print(f"Генерация {DAYS_COUNT} дней по {FLIGHTS_PER_DAY} рейсов...")
    for day in range(DAYS_COUNT):
        current_date = START_DATE + timedelta(days=day)
        
        for _ in range(FLIGHTS_PER_DAY):
            # Выбираем случайные аэропорты (вылет и прилет не должны совпадать)
            origin, destination = random.sample(AIRPORTS, 2)
            
            # Случайное время вылета в течение дня (от 00:00 до 23:59)
            departure_hour = random.randint(0, 23)
            departure_minute = random.randint(0, 59)
            departure_time = current_date.replace(hour=departure_hour, minute=departure_minute)
            
            # Время полета от 1 до 6 часов (требование задачи)
            duration_hours = random.randint(1, 6)
            arrival_time = departure_time + timedelta(hours=duration_hours)
            
            # Случайная цена от 3000 до 30000 (округленная до сотен)
            price = float(random.randint(30, 300) * 100)
            
            flights_data.append({
                "carrier": random.choice(CARRIERS),
                "flight_number": f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.randint(100, 999)}",
                "origin": origin,
                "destination": destination,
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "price": price
            })

    # 4. Вставка данных в базу
    print("Загрузка данных в базу...")
    with engine.begin() as connection:  # begin() открывает транзакцию и сам делает commit
        connection.execute(flights_table.insert(), flights_data)
    
    print(f"Успешно загружено {len(flights_data)} рейсов!")

if __name__ == "__main__":
    generate_and_load_data()