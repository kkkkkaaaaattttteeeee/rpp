import asyncio
import httpx
import time
import random
import argparse
import statistics

# Глобальные списки для сбора метрик
search_latencies = []
health_latencies = []
search_errors = 0
health_errors = 0

def calculate_percentile(data, p):
    """Вычисление процентиля (p50, p95, p99)"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = int(len(sorted_data) * (p / 100.0))
    # Защита от выхода за границы списка
    index = min(index, len(sorted_data) - 1)
    return sorted_data[index]

def print_stats(title, latencies, total_requests, duration, errors):
    """Вывод красивой статистики в терминал"""
    if not latencies:
        print(f"\n=== {title} ===")
        print("Нет данных (все запросы упали или не были выполнены).")
        return

    p50 = calculate_percentile(latencies, 50)
    p95 = calculate_percentile(latencies, 95)
    p99 = calculate_percentile(latencies, 99)
    max_time = max(latencies)
    rps = total_requests / duration
    error_rate = (errors / total_requests * 100) if total_requests > 0 else 0

    print(f"\n=== {title} ===")
    print(f"Всего запросов: {total_requests}")
    print(f"RPS: {rps:.2f}")
    print(f"p50: {p50:.2f} мс")
    print(f"p95: {p95:.2f} мс")
    print(f"p99: {p99:.2f} мс")
    print(f"Max: {max_time:.2f} мс")
    print(f"Ошибки: {error_rate:.2f}%")

async def do_search(client, url, date, origin, dest):
    """Выполняет один запрос поиска и записывает метрики"""
    global search_errors
    start_time = time.perf_counter()
    try:
        # Таймаут клиента 30 секунд (из требований)
        response = await client.get(f"{url}/search", params={"origin": origin, "destination": dest, "date": date}, timeout=30.0)
        latency = (time.perf_counter() - start_time) * 1000 # перевод в мс
        
        if response.status_code == 200:
            search_latencies.append(latency)
        else:
            search_errors += 1
    except Exception:
        search_errors += 1

async def health_checker(client, url, stop_event):
    """Фоновый процесс: опрашивает /health каждые 100 мс"""
    global health_errors
    while not stop_event.is_set():
        start_time = time.perf_counter()
        try:
            response = await client.get(f"{url}/health", timeout=5.0)
            latency = (time.perf_counter() - start_time) * 1000
            if response.status_code == 200:
                health_latencies.append(latency)
            else:
                health_errors += 1
        except Exception:
            health_errors += 1
        
        # Ждем 100 мс (минус время, потраченное на сам запрос)
        elapsed = time.perf_counter() - start_time
        sleep_time = max(0, 0.1 - elapsed)
        await asyncio.sleep(sleep_time)

async def closed_client(client, url, date, origin, dest, stop_event):
    """Замкнутый режим: клиент шлет запрос, ждет ответ, шлет следующий"""
    while not stop_event.is_set():
        await do_search(client, url, date, origin, dest)
        # В замкнутом режиме паузы нет, следующий запрос сразу после ответа
        await asyncio.sleep(0)

async def open_generator(client, url, date, origin, dest, target_rps, stop_event):
    """Открытый режим: генерация запросов с экспоненциальным интервалом"""
    tasks = []
    while not stop_event.is_set():
        # Экспоненциальное распределение для интервала
        interval = random.expovariate(target_rps)
        await asyncio.sleep(interval)
        
        if not stop_event.is_set():
            # Создаем задачу "выстрелил и забыл", чтобы не блокировать генератор
            task = asyncio.create_task(do_search(client, url, date, origin, dest))
            tasks.append(task)
            
    # Ждем завершения всех оставшихся запросов
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def run_load_test(args):
    global search_latencies, health_latencies, search_errors, health_errors
    # Сброс метрик
    search_latencies.clear()
    health_latencies.clear()
    search_errors = 0
    health_errors = 0

    async with httpx.AsyncClient() as client:
        stop_event = asyncio.Event()
        
        # 1. Запуск фонового опроса /health
        health_task = asyncio.create_task(health_checker(client, args.url, stop_event))

        # 2. Запуск генерации нагрузки (в зависимости от режима)
        workers = []
        if args.mode == "closed":
            print(f"Запуск ЗАМКНУТОГО режима с {args.clients} клиентами...")
            for _ in range(args.clients):
                workers.append(asyncio.create_task(closed_client(client, args.url, args.date, args.origin, args.dest, stop_event)))
        elif args.mode == "open":
            print(f"Запуск ОТКРЫТОГО режима с интенсивностью {args.rps} RPS...")
            workers.append(asyncio.create_task(open_generator(client, args.url, args.date, args.origin, args.dest, args.rps, stop_event)))

        # 3. Ожидание прогрева (warm-up)
        if args.warmup > 0:
            print(f"Прогрев {args.warmup} секунд...")
            await asyncio.sleep(args.warmup)
            # Очищаем списки после прогрева, чтобы не портить статистику
            search_latencies.clear()
            health_latencies.clear()
            search_errors = 0
            health_errors = 0

        # 4. Основной замер
        print(f"Основной замер {args.duration} секунд...")
        await asyncio.sleep(args.duration)

        # 5. Остановка всех процессов
        stop_event.set()
        for w in workers:
            w.cancel()
        health_task.cancel()
        
        # Даем время на завершение
        await asyncio.gather(health_task, *workers, return_exceptions=True)

    # 6. Вывод результатов
    print_stats("ПОИСК (/search)", search_latencies, len(search_latencies) + search_errors, args.duration, search_errors)
    print_stats("ЗДОРОВЬЕ (/health)", health_latencies, len(health_latencies) + health_errors, args.duration, health_errors)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Нагрузочный скрипт для агрегатора авиабилетов")
    parser.add_argument("--url", default="http://localhost:8000", help="Базовый URL сервиса")
    parser.add_argument("--mode", choices=["closed", "open"], required=True, help="Режим нагрузки")
    parser.add_argument("--clients", type=int, default=1, help="Количество клиентов (для closed)")
    parser.add_argument("--rps", type=float, default=5.0, help="Запросов в секунду (для open)")
    parser.add_argument("--duration", type=int, default=60, help="Длительность замера, сек")
    parser.add_argument("--warmup", type=int, default=10, help="Длительность прогрева, сек")
    parser.add_argument("--origin", default="AP1", help="Аэропорт вылета")
    parser.add_argument("--dest", default="AP5", help="Аэропорт прилета")
    parser.add_argument("--date", default="2026-08-01", help="Дата вылета")
    
    args = parser.parse_args()
    asyncio.run(run_load_test(args))