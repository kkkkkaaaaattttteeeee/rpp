from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .exceptions import DomainInvariantViolation
from .value_objects import ScooterId, TripId, UserId, BatteryLevel, Money, TimeRange, ScooterState

MIN_BATTERY_TO_RENT = 20

@dataclass
class Scooter:
    id: ScooterId
    battery: BatteryLevel
    state: ScooterState = ScooterState.FREE

    def is_available(self) -> bool:
        return (self.state == ScooterState.FREE
                and not self.battery.is_below(MIN_BATTERY_TO_RENT))

    def mark_rented(self) -> None:
        if self.state != ScooterState.FREE:
            raise DomainInvariantViolation(f"Самокат не свободен: {self.state.value}")
        if self.battery.is_below(MIN_BATTERY_TO_RENT):
            raise DomainInvariantViolation(f"Заряд {self.battery.percent}% ниже порога")
        self.state = ScooterState.RENTED

@dataclass
class Trip:
    id: TripId
    scooter_id: ScooterId
    user_id: UserId
    started_at: datetime
    time_range: Optional[TimeRange] = None
    cost: Optional[Money] = None

    def is_active(self) -> bool:
        return self.time_range is None