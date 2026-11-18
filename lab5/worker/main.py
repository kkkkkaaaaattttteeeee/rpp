import asyncio
import json
import os
from decimal import Decimal
from datetime import datetime
import aio_pika
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from models import Base, Account, Operation
from domain import process_operation

DATABASE_URL = os.getenv("DATABASE_URL")
RABBITMQ_URL = os.getenv("RABBITMQ_URL")

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def setup_rabbitmq(channel):
    # 1. Объявляем обменник и очередь для операций (direct)
    exchange = await channel.declare_exchange("loyalty", aio_pika.ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue("operations", durable=True, arguments={"x-queue-type": "quorum"})
    await queue.bind(exchange, routing_key="operation")

    # 2. Объявляем обменник и очереди для событий (fanout)
    events_exchange = await channel.declare_exchange("loyalty.events", aio_pika.ExchangeType.FANOUT, durable=True)
    notifier_queue = await channel.declare_queue("notifier.events", durable=True, arguments={"x-queue-type": "quorum"})
    analytics_queue = await channel.declare_queue("analytics.events", durable=True, arguments={"x-queue-type": "quorum"})
    
    await notifier_queue.bind(events_exchange)
    await analytics_queue.bind(events_exchange)
    
    return queue, events_exchange

async def process_message(message: aio_pika.IncomingMessage, events_exchange):
    async with message.process(requeue=False): # Если упадем, сообщение не вернется в очередь само
        data = json.loads(message.body.decode())
        op_id = data["operation_id"]
        
        async with async_session() as session:
            async with session.begin():
                # Проверка на дубликат обработки (идемпотентность)
                existing_op = await session.get(Operation, op_id)
                if existing_op:
                    return # Уже обработано, просто выходим (process сделает ack)

                # Получаем или создаем аккаунт
                account = await session.get(Account, data["customer_id"])
                if not account:
                    account = Account(customer_id=data["customer_id"], balance=Decimal('0.00'))
                    session.add(account)

                # Подготовка данных для домена
                op_type = data["type"]
                amount = Decimal(data["amount"]) if data.get("amount") else None
                points = data.get("points")
                
                # Поиск существующей покупки для возврата
                existing_purchase = None
                is_already_returned = False
                if op_type == "return":
                    stmt = select(Operation).where(
                        Operation.check_number == data["check_number"],
                        Operation.type == "purchase",
                        Operation.status == "applied"
                    )
                    res = await session.execute(stmt)
                    existing_purchase = res.scalar_one_or_none()
                    
                    if existing_purchase:
                        if existing_purchase.customer_id != data["customer_id"]:
                            # Приоритет ошибок: customer_mismatch идет после purchase_not_found
                            result = type('obj', (object,), {'status': 'rejected', 'points_delta': 0, 'new_balance': account.balance, 'reject_reason': 'customer_mismatch'})
                        else:
                            # Проверяем, был ли уже возврат
                            stmt_ret = select(Operation).where(
                                Operation.check_number == data["check_number"],
                                Operation.type == "return",
                                Operation.status == "applied"
                            )
                            res_ret = await session.execute(stmt_ret)
                            is_already_returned = res_ret.scalar_one_or_none() is not None
                            result = process_operation(op_type, amount, points, account.balance, existing_purchase, is_already_returned)
                    else:
                        result = process_operation(op_type, amount, points, account.balance)
                else:
                    result = process_operation(op_type, amount, points, account.balance, existing_purchase)

                # Если операция отклонена по customer_mismatch (костыль для чистоты домена)
                if 'result' not in locals() or isinstance(result, type) or not hasattr(result, 'status'):
                     from domain import ProcessResult
                     result = ProcessResult("rejected", 0, account.balance, "customer_mismatch")

                # Сохраняем результат
                new_op = Operation(
                    operation_id=op_id,
                    type=op_type,
                    customer_id=data["customer_id"],
                    store_id=data["store_id"],
                    check_number=data["check_number"],
                    amount=amount,
                    points_delta=result.points_delta,
                    balance_after=result.new_balance,
                    status=result.status,
                    reject_reason=result.reject_reason,
                    occurred_at=datetime.fromisoformat(data["occurred_at"])
                )
                session.add(new_op)
                
                if result.status == "applied":
                    account.balance = result.new_balance

        # --- ТРАНЗАКЦИЯ ЗАВЕРШЕНА И ЗАФИКСИРОВАНА ---

        # Публикуем событие
        event_payload = {
            "operation_id": op_id,
            "type": op_type,
            "customer_id": data["customer_id"],
            "store_id": data["store_id"],
            "status": result.status,
            "points_delta": result.points_delta,
            "balance_after": str(result.new_balance),
            "reject_reason": result.reject_reason,
            "processed_at": datetime.utcnow().isoformat()
        }
        
        event_msg = aio_pika.Message(
            body=json.dumps(event_payload).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=op_id
        )
        
        # Публикуем в fanout, ждем подтверждения
        await events_exchange.publish(event_msg, routing_key="", mandatory=True)
        
        # message.process() автоматически сделает ACK только после выхода из блока


async def main():
    # Создание таблиц
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    async with connection:
        channel = await connection.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=1)
        
        queue, events_exchange = await setup_rabbitmq(channel)
        
        print("Worker started. Waiting for messages...")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    await process_message(message, events_exchange)
                except Exception as e:
                    print(f"Error processing message: {e}")
                    # Если произошла ошибка, сообщение будет отклонено (nack) 
                    # благодаря message.process(requeue=False) в случае падения

if __name__ == "__main__":
    asyncio.run(main())