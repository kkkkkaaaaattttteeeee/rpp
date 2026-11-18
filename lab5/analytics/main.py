import os
import json
import asyncio
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI, HTTPException
from collections import defaultdict

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Хранилище в памяти
# store_id -> { stats }
stores_db = {}
stats = {"received": 0}

async def consume_events():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        
        exchange = await channel.declare_exchange("loyalty.events", aio_pika.ExchangeType.FANOUT, durable=True)
        queue = await channel.declare_queue("analytics.events", durable=True, arguments={"x-queue-type": "quorum"})
        await queue.bind(exchange)

        print("Analytics started. Waiting for events...")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    data = json.loads(message.body.decode("utf-8"))
                    stats["received"] += 1
                    
                    store_id = data["store_id"]
                    if store_id not in stores_db:
                        stores_db[store_id] = {
                            "purchase_applied": 0,
                            "return_applied": 0,
                            "redeem_applied": 0,
                            "rejected_total": 0,
                            "points_earned": 0,
                            "points_returned": 0,
                            "points_redeemed": 0
                        }
                    
                    store = stores_db[store_id]
                    
                    if data["status"] == "rejected":
                        store["rejected_total"] += 1
                    else:
                        op_type = data["type"]
                        delta = data["points_delta"]
                        
                        if op_type == "purchase":
                            store["purchase_applied"] += 1
                            store["points_earned"] += delta
                        elif op_type == "return":
                            store["return_applied"] += 1
                            store["points_returned"] += abs(delta)
                        elif op_type == "redeem":
                            store["redeem_applied"] += 1
                            store["points_redeemed"] += abs(delta)
                            
                    print(f"[ANALYTICS] Updated stats for store {store_id}")


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

@app.get("/stores")
async def get_all_stores():
    return [{"store_id": k, **v} for k, v in stores_db.items()]

@app.get("/stores/{store_id}")
async def get_store(store_id: str):
    if store_id not in stores_db:
        raise HTTPException(status_code=404, detail="Store not found")
    return {"store_id": store_id, **stores_db[store_id]}

@app.get("/stats")
async def get_stats():
    return stats