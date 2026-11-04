from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from .exceptions import InvalidValueObject

# ИСПРАВЛЕНИЕ ЗАМЕЧАНИЯ 1: ID как объекты-значения
@dataclass(frozen=True)
class ScooterId:
    value: str
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise InvalidValueObject("ID самоката не может быть пустым")

@dataclass(frozen=True)
class TripId:
    value: str
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise InvalidValueObject("ID поездки не может быть пустым")

@dataclass(frozen=True)
class UserId:
    value: str
    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise InvalidValueObject("ID пользователя не может быть пустым")

# ОБЪЕКТЫ-ЗНАЧЕНИЯ ИЗ ЛР2
class ScooterState(Enum):
    FREE = "free"
    RENTED = "rented"
    MAINTENANCE = "maintenance"

@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "RUB"
    def __post_init__(self):
        if self.amount < 0:
            raise InvalidValueObject("Сумма не может быть отрицательной")

@dataclass(frozen=True)
class BatteryLevel:
    percent: int
    def __post_init__(self):
        if not 0 <= self.percent <= 100:
            raise InvalidValueObject("Заряд должен быть от 0 до 100")
    def is_below(self, threshold: int) -> bool:
        return self.percent < threshold

@dataclass(frozen=True)
class TimeRange:
    start: datetime
    end: datetime
    def __post_init__(self):
        if self.end <= self.start:
            raise InvalidValueObject("Конец должен быть позже начала")
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

@dataclass(frozen=True)
class Tariff:
    price_per_minute: Money
    minimum_cost: Money
    def __post_init__(self):
        if self.price_per_minute.currency != self.minimum_cost.currency:
            raise InvalidValueObject("Валюты тарифа должны совпадать")