from typing import TYPE_CHECKING
from domain.exceptions import TransitionNotAllowed

if TYPE_CHECKING:
    from domain.aggregates import Trip

class TripState:
    """Базовый класс. По умолчанию запрещено всё."""
    name: str = ""
    allowed: frozenset[str] = frozenset()  # База: пустой список

    def start_ride(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "start_ride")
    def pause_ride(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "pause_ride")
    def resume_ride(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "resume_ride")
    def finish_ride(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "finish_ride")
    def pay(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "pay")
    def expire_booking(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "expire_booking")
    def fail_payment(self, trip: "Trip") -> "TripState":
        raise TransitionNotAllowed(self.name, "fail_payment")

class Booked(TripState):
    name = "Забронирована"
    allowed = frozenset({"start_ride", "expire_booking"})
    def start_ride(self, trip: "Trip") -> "TripState":
        return Started()
    def expire_booking(self, trip: "Trip") -> "TripState":
        return Cancelled()

class Started(TripState):
    name = "Начата"
    allowed = frozenset({"pause_ride", "finish_ride"})
    def pause_ride(self, trip: "Trip") -> "TripState":
        return Paused()
    def finish_ride(self, trip: "Trip") -> "TripState":
        return Finished()

class Paused(TripState):
    name = "Приостановлена"
    allowed = frozenset({"resume_ride", "finish_ride"})
    def resume_ride(self, trip: "Trip") -> "TripState":
        return Started()
    def finish_ride(self, trip: "Trip") -> "TripState":
        return Finished()

class Finished(TripState):
    name = "Завершена"
    allowed = frozenset({"pay", "fail_payment"})
    def pay(self, trip: "Trip") -> "TripState":
        return Paid()
    def fail_payment(self, trip: "Trip") -> "TripState":
        return Blocked()

# Конечные состояния (allowed убран, так как он пуст по умолчанию)
class Paid(TripState):
    name = "Оплачена"

class Cancelled(TripState):
    name = "Отменена"

class Blocked(TripState):
    name = "Заблокирована"
