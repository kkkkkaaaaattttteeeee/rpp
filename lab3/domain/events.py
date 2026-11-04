from dataclasses import dataclass
from datetime import datetime
from domain.value_objects import TripId, Money

@dataclass(frozen=True)
class TripBooked:
    trip_id: TripId
    occurred_at: datetime

@dataclass(frozen=True)
class TripStarted:
    trip_id: TripId
    occurred_at: datetime

@dataclass(frozen=True)
class TripPaused:
    trip_id: TripId
    occurred_at: datetime

@dataclass(frozen=True)
class TripFinished:
    trip_id: TripId
    cost: Money
    occurred_at: datetime

@dataclass(frozen=True)
class TripPaid:
    trip_id: TripId
    occurred_at: datetime

@dataclass(frozen=True)
class TripBlocked:
    trip_id: TripId
    occurred_at: datetime

@dataclass(frozen=True)
class BookingExpired:
    trip_id: TripId
    occurred_at: datetime