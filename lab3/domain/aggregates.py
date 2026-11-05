from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .exceptions import DomainInvariantViolation
from .value_objects import ScooterId, TripId, UserId, BatteryLevel, Money, TimeRange, ScooterState
from .states import TripState, Booked
from .events import TripBooked, TripStarted, TripPaused, TripFinished, TripPaid, TripBlocked, BookingExpired

MIN_BATTERY_TO_RENT = 20

@dataclass
class Scooter:
    id: ScooterId
    battery: BatteryLevel
    state: ScooterState = ScooterState.FREE

    def is_available(self) -> bool:
        return (self.state == ScooterState.FREE and not self.battery.is_below(MIN_BATTERY_TO_RENT))
    def mark_rented(self) -> None:
        if self.state != ScooterState.FREE:
            raise DomainInvariantViolation(f"Самокат не свободен: {self.state.value}")
        if self.battery.is_below(MIN_BATTERY_TO_RENT):
            raise DomainInvariantViolation(f"Заряд {self.battery.percent}% ниже порога")
        self.state = ScooterState.RENTED
    def mark_returned(self, battery_after: BatteryLevel) -> None:
        if self.state != ScooterState.RENTED:
            raise DomainInvariantViolation("Самокат не в аренде")
        self.battery = battery_after
        self.state = ScooterState.FREE

@dataclass
class Trip:
    id: TripId
    scooter_id: ScooterId
    user_id: UserId
    created_at: datetime
    started_at: Optional[datetime] = None
    time_range: Optional[TimeRange] = None
    cost: Optional[Money] = None
    
    # НОВЫЕ ПОЛЯ ДЛЯ ПАУЗЫ
    paused_at: Optional[datetime] = None
    total_pause_minutes: int = 0

    _state: TripState = field(init=False, default_factory=Booked)
    _events: list = field(init=False, default_factory=list)

    def __post_init__(self):
        self._events.append(TripBooked(self.id, self.created_at))

    @property
    def status(self) -> str:
        return self._state.name
    @property
    def allowed_events(self) -> frozenset[str]:
        return self._state.allowed
    @property
    def events(self) -> tuple:
        return tuple(self._events)

    def start_ride(self, at: datetime) -> None:
        self._state = self._state.start_ride(self)
        self.started_at = at
        self._events.append(TripStarted(self.id, at))

    def pause_ride(self, at: datetime) -> None:
        self._state = self._state.pause_ride(self)
        self.paused_at = at  # Фиксируем время начала паузы
        self._events.append(TripPaused(self.id, at))

    def resume_ride(self, at: datetime) -> None:
        self._state = self._state.resume_ride(self)
        if self.paused_at:
            # Считаем, сколько минут длилась пауза, и прибавляем к общему счетчику
            pause_duration = int((at - self.paused_at).total_seconds() // 60)
            self.total_pause_minutes += pause_duration
            self.paused_at = None # Сбрасываем

    def finish_ride(self, at: datetime, cost: Money) -> None:
        new_state = self._state.finish_ride(self)
        self.time_range = TimeRange(start=self.started_at, end=at)
        self.cost = cost
        self._state = new_state
        self._events.append(TripFinished(self.id, cost, at))

    def pay(self, at: datetime) -> None:
        self._state = self._state.pay(self)
        self._events.append(TripPaid(self.id, at))

    def fail_payment(self, at: datetime) -> None:
        self._state = self._state.fail_payment(self)
        self._events.append(TripBlocked(self.id, at))

    def on_expire_booking(self, now: datetime) -> None:
        if self._state.name != "Забронирована":
            return
        if now - self.created_at >= timedelta(minutes=10):
            self._state = self._state.expire_booking(self)
            self._events.append(BookingExpired(self.id, now))
