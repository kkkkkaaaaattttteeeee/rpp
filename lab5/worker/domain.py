from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProcessResult:
    status: str
    points_delta: int
    new_balance: Decimal
    reject_reason: Optional[str] = None

def process_operation(
    op_type: str,
    amount: Optional[Decimal],
    points: Optional[int],
    current_balance: Decimal,
    # Для возвратов нам нужно знать состояние предыдущей покупки
    existing_purchase: Optional[object] = None, 
    is_already_returned: bool = False
) -> ProcessResult:
    
    if op_type == "purchase":
        # Проверка на дубликат (передается снаружи, если чек уже есть)
        if existing_purchase is not None:
            return ProcessResult("rejected", 0, current_balance, "duplicate_purchase")
        
        # 5% от суммы, дробная часть отбрасывается
        points_to_add = int(amount * Decimal('0.05'))
        new_balance = current_balance + points_to_add
        return ProcessResult("applied", points_to_add, new_balance)

    elif op_type == "return":
        if existing_purchase is None:
            return ProcessResult("rejected", 0, current_balance, "purchase_not_found")
        
        if existing_purchase.customer_id != existing_purchase.customer_id: # Заглушка, логика ниже
            pass # В реальности проверка идет в main.py по customer_id текущей операции
            
        if is_already_returned:
            return ProcessResult("rejected", 0, current_balance, "already_returned")
        
        # Списываем столько, сколько было начислено за покупку
        points_to_remove = existing_purchase.points_delta
        new_balance = current_balance - points_to_remove
        return ProcessResult("applied", -points_to_remove, new_balance)

    elif op_type == "redeem":
        # Лимит 30% от суммы чека
        max_allowed = amount * Decimal('0.30')
        if Decimal(points) > max_allowed:
            return ProcessResult("rejected", 0, current_balance, "limit_exceeded")
        
        if Decimal(points) > current_balance:
            return ProcessResult("rejected", 0, current_balance, "insufficient_balance")
        
        new_balance = current_balance - Decimal(points)
        return ProcessResult("applied", -points, new_balance)

    return ProcessResult("rejected", 0, current_balance, "unknown_type")