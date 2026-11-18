from pydantic import BaseModel, Field, field_validator
from typing import Optional

class OperationCreate(BaseModel):
    operation_id: str
    type: str
    customer_id: str
    store_id: str
    check_number: str
    occurred_at: str
    amount: Optional[str] = None
    points: Optional[int] = None

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        if v not in ['purchase', 'return', 'redeem']:
            raise ValueError('Invalid type')
        return v

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v, info):
        # Для purchase и redeem amount обязателен и положителен
        op_type = info.data.get('type')
        if op_type in ['purchase', 'redeem']:
            if v is None:
                raise ValueError('Amount is required')
            try:
                if float(v) <= 0:
                    raise ValueError('Amount must be positive')
            except ValueError:
                raise ValueError('Amount must be a valid number')
        return v

    @field_validator('points')
    @classmethod
    def validate_points(cls, v, info):
        # Для redeem points обязателен и положителен
        op_type = info.data.get('type')
        if op_type == 'redeem':
            if v is None or v <= 0:
                raise ValueError('Points must be positive and required')
        return v