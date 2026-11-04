from typing import TYPE_CHECKING
from domain.exceptions import TransitionNotAllowed

if TYPE_CHECKING:
    from domain.aggregates import Trip

class TripState:
    """Базовый класс состояния поездки. Все события по умолчанию запрещены."""
    name: str = ""
    allowed: frozenset[str] = frozenset()

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
    """Забронирована. Допустимые события: начало поездки, истечение времени брони."""
    name = "Забронирована"
    allowed = frozenset({"start_ride", "expire_booking"})

    def start_ride(self, trip: "Trip") -> "TripState":
        return Started()

    def expire_booking(self, trip: "Trip") -> "TripState":
        return Cancelled()


class Started(TripState):
    """Начата. Допустимые события: пауза, завершение."""
    name = "Начата"
    allowed = frozenset({"pause_ride", "finish_ride"})

    def pause_ride(self, trip: "Trip") -> "TripState":
        return Paused()

    def finish_ride(self, trip: "Trip") -> "TripState":
        return Finished()


class Paused(TripState):
    """Приостановлена. Допустимые события: возобновление, завершение."""
    name = "Приостановлена"
    allowed = frozenset({"resume_ride", "finish_ride"})

    def resume_ride(self, trip: "Trip") -> "TripState":
        return Started()

    def finish_ride(self, trip: "Trip") -> "TripState":
        return Finished()


class Finished(TripState):
    """Завершена. Допустимые события: оплата, ошибка оплаты."""
    name = "Завершена"
    allowed = frozenset({"pay", "fail_payment"})

    def pay(self, trip: "Trip") -> "TripState":
        return Paid()

    def fail_payment(self, trip: "Trip") -> "TripState":
        return Blocked()


# Конечные состояния (из них нет переходов)

class Paid(TripState):
    name = "Оплачена"
    allowed = frozenset()

class Cancelled(TripState):
    name = "Отменена"
    allowed = frozenset()

class Blocked(TripState):
    name = "Заблокирована"
    allowed = frozenset()