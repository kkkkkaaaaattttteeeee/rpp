from datetime import datetime
from typing import Protocol

class Clock(Protocol):
    """Порт для получения текущего времени."""
    def now(self) -> datetime: ...

class SystemClock:
    """Реальная реализация часов (для продакшена)."""
    def now(self) -> datetime:
        return datetime.now()