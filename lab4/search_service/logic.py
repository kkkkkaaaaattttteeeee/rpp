from datetime import datetime
from collections import defaultdict

def build_routes(all_flights: list, origin: str, destination: str):
    """
    Ищет маршруты до 2 пересадок из origin в destination.
    Возвращает топ-20 самых дешевых маршрутов.
    """
    # Группируем рейсы по аэропорту вылета для быстрого поиска
    by_origin = defaultdict(list)
    for f in all_flights:
        # Приводим время из строки к объекту datetime
        if isinstance(f['departure_time'], str):
            f['departure_time'] = datetime.fromisoformat(f['departure_time'].replace('Z', '+00:00'))
            f['arrival_time'] = datetime.fromisoformat(f['arrival_time'].replace('Z', '+00:00'))
        by_origin[f['origin']].append(f)

    routes = []

    # Функция проверки стыковки (от 1 до 6 часов)
    def is_valid_transfer(arrival, next_departure):
        diff_hours = (next_departure - arrival).total_seconds() / 3600.0
        return 1.0 <= diff_hours <= 6.0

    # 1. Прямые рейсы (0 пересадок)
    for f1 in by_origin[origin]:
        if f1['destination'] == destination:
            routes.append({"flights": [f1], "price": f1['price']})

    # 2. Рейсы с 1 пересадкой
    for f1 in by_origin[origin]:
        if f1['destination'] == destination: continue # Исключаем петли
        for f2 in by_origin[f1['destination']]:
            if f2['destination'] == destination:
                if is_valid_transfer(f1['arrival_time'], f2['departure_time']):
                    routes.append({"flights": [f1, f2], "price": f1['price'] + f2['price']})

    # 3. Рейсы с 2 пересадками
    for f1 in by_origin[origin]:
        for f2 in by_origin[f1['destination']]:
            if not is_valid_transfer(f1['arrival_time'], f2['departure_time']): continue
            if len({f1['origin'], f1['destination'], f2['destination']}) < 3: continue # Аэропорты не повторяются
            for f3 in by_origin[f2['destination']]:
                if f3['destination'] == destination:
                    if is_valid_transfer(f2['arrival_time'], f3['departure_time']):
                        routes.append({"flights": [f1, f2, f3], "price": f1['price'] + f2['price'] + f3['price']})

    # Сортируем по цене и отдаем топ-20
    routes.sort(key=lambda x: x['price'])
    return routes[:20]