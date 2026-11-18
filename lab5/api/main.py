import os
import json
from datetime import datetime
import aio_pika
from fastapi import FastAPI, HTTPException, status
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, desc
from models import Account, Operation
from schemas import OperationCreate

DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")

app = FastAPI(title="Loyalty API")

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Глобальные переменные для подключений
rabbit_connection = None
rabbit_channel = None
loyalty_exchange = None

@app.on_event("startup")
async def startup():
    global rabbit_connection, rabbit_channel, loyalty_exchange
    # Подключаемся к RabbitMQ
    rabbit_connection = await aio_pika.connect_robust(RABBITMQ_URL)
    rabbit_channel = await rabbit_connection.channel(publisher_confirms=True)
    
    # Объявляем обменник (на случай, если воркер еще не успел)
    loyalty_exchange = await rabbit_channel.declare_exchange(
        "loyalty", aio_pika.ExchangeType.DIRECT, durable=True
    )

@app.on_event("shutdown")
async def shutdown():
    if rabbit_connection:
        await rabbit_connection.close()

@app.post("/operations", status_code=status.HTTP_202_ACCEPTED)
async def create_operation(op: OperationCreate):
    # Pydantic уже проверил формат, возвращаем 422 при ошибке (автоматически FastAPI)
    
    message = aio_pika.Message(
        body=op.model_dump_json().encode("utf-8"),
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        message_id=op.operation_id
    )
    
    try:
        # Публикуем в loyalty с ключом operation
        await loyalty_exchange.publish(message, routing_key="operation", mandatory=True)
    except Exception as e:
        # Если брокер не подтвердил публикацию
        raise HTTPException(status_code=503, detail="Broker unavailable")

    return {"operation_id": op.operation_id}

@app.get("/operations/{operation_id}")
async def get_operation(operation_id: str):
    async with async_session() as session:
        op = await session.get(Operation, operation_id)
        if not op:
            raise HTTPException(status_code=404, detail="Operation not found or not processed yet")
        
        return {
            "operation_id": op.operation_id,
            "status": op.status,
            "points_delta": op.points_delta,
            "balance_after": str(op.balance_after),
            "reject_reason": op.reject_reason
        }

@app.get("/accounts/{customer_id}")
async def get_account(customer_id: str):
    async with async_session() as session:
        account = await session.get(Account, customer_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Достаем последние 20 операций
        stmt = select(Operation).where(Operation.customer_id == customer_id).order_by(desc(Operation.processed_at)).limit(20)
        result = await session.execute(stmt)
        ops = result.scalars().all()
        
        return {
            "customer_id": account.customer_id,
            "balance": str(account.balance),
            "operations": [
                {
                    "operation_id": o.operation_id,
                    "type": o.type,
                    "status": o.status,
                    "points_delta": o.points_delta,
                    "processed_at": o.processed_at.isoformat()
                } for o in ops
            ]
        }

@app.get("/health")
async def health_check():
    # Проверка БД
    try:
        async with async_session() as session:
            await session.execute(select(1))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    
    # Проверка брокера
    if rabbit_connection.is_closed:
        raise HTTPException(status_code=503, detail="RabbitMQ unavailable")
        
    return {"status": "ok"}