import os
import json
import asyncio
import random
from datetime import datetime
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI, Query
from collections import defaultdict

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
MIN_DELAY_MS = int(os.getenv("MIN_DELAY_MS", "200"))
MAX_DELAY_MS = int(os.getenv("MAX_DELAY_MS", "1500"))
UNSUBSCRIBED = set(filter(None, os.getenv("UNSUBSCRIBED", "").split(",")))

# Хранилище в памяти
notifications_db = defaultdict(list)
stats = {"received": 0, "sent": 0}

async def consume_events():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        exchange = await channel.declare_exchange("loyalty.events", aio_pika.ExchangeType.FANOUT, durable=True)
        queue = await channel.declare_queue("notifier.events", durable=True, arguments={"x-queue-type": "quorum"})
        await queue.bind(exchange)

        print("Notifier started. Waiting for events...")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body.decode("utf-8"))
                    stats["received"] += 1
                    
                    customer_id = data["customer_id"]
                    if customer_id in UNSUBSCRIBED:
                        continue # Пропускаем отписавшихся
                    
                    # Формируем текст
                    if data["status"] == "rejected":
                        text = f"Операция отклонена: {data['reject_reason']}"
                    else:
                        delta = data["points_delta"]
                        balance = data["balance_after"]
                        if delta > 0:
                            text = f"Начислено {delta} баллов, баланс {balance}"
                        else:
                            text = f"Списано {abs(delta)} баллов, баланс {balance}"
                    
                    # Имитация задержки отправки
                    delay = random.uniform(MIN_DELAY_MS, MAX_DELAY_MS) / 1000.0
                    await asyncio.sleep(delay)
                    
                    # Сохраняем и логируем
                    record = {
                        "operation_id": data["operation_id"],
                        "text": text,
                        "sent_at": datetime.utcnow().isoformat()
                    }
                    notifications_db[customer_id].append(record)
                    stats["sent"] += 1
                    print(f"[NOTIFICATION to {customer_id}]: {text}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(consume_events())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.get("/notifications")
async def get_notifications(customer_id: str = Query(...)):
    return notifications_db.get(customer_id, [])

@app.get("/stats")
async def get_stats():
    return stats