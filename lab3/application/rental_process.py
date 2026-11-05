from datetime import datetime
from typing import Optional

from domain.aggregates import Scooter, Trip
from domain.value_objects import ScooterId, TripId, UserId, Money, Tariff, TimeRange, BatteryLevel
from domain.repositories import ScooterRepository, TripRepository
from domain.exceptions import DomainInvariantViolation, GatewayUnresolved

from infrastructure.clock import Clock
from infrastructure.payment_gateway import PaymentGateway
from application.predicates import RentalPredicates

class RentalProcess:
    """
    Прикладной сервис для процесса Аренды самоката.
    """
    def __init__(
        self, 
        scooter_repo: ScooterRepository, 
        trip_repo: TripRepository, 
        payment_gateway: PaymentGateway,
        clock: Clock,
        user_repo,
        tariff: Tariff
    ):
        self.scooter_repo = scooter_repo
        self.trip_repo = trip_repo
        self.payment_gateway = payment_gateway
        self.clock = clock
        self.user_repo = user_repo
        self.tariff = tariff
        
        self.predicates = RentalPredicates(user_repo, payment_gateway)

    def _get_trip(self, trip_id: TripId) -> Trip:
        trip = self.trip_repo.get(trip_id)
        if not trip:
            raise ValueError(f"Поездка {trip_id.value} не найдена")
        return trip

    def _get_scooter(self, scooter_id: ScooterId) -> Scooter:
        scooter = self.scooter_repo.get(scooter_id)
        if not scooter:
            raise ValueError(f"Самокат {scooter_id.value} не найден")
        return scooter

    def book_scooter(self, trip_id: TripId, scooter_id: ScooterId, user_id: UserId) -> None:
        now = self.clock.now()
        trip = Trip(
            id=trip_id, 
            scooter_id=scooter_id, 
            user_id=user_id, 
            created_at=now
        )
        self.trip_repo.save(trip)

    def start_ride(self, trip_id: TripId, scooter_id: ScooterId) -> None:
        trip = self._get_trip(trip_id)
        scooter = self._get_scooter(scooter_id)
        now = self.clock.now()

        if not self.predicates.is_debt_free(trip.user_id):
            raise GatewayUnresolved("Есть задолженность")
            
        if not self.predicates.is_payment_authorized(Money(300)):
            raise GatewayUnresolved("Платёж не авторизован")

        trip.start_ride(at=now)
        scooter.mark_rented()

        self.trip_repo.save(trip)
        self.scooter_repo.save(scooter)

    def pause_ride(self, trip_id: TripId) -> None:
        trip = self._get_trip(trip_id)
        trip.pause_ride(at=self.clock.now())
        self.trip_repo.save(trip)

    def resume_ride(self, trip_id: TripId) -> None:
        trip = self._get_trip(trip_id)
        trip.resume_ride(at=self.clock.now())
        self.trip_repo.save(trip)

    def upload_photo(self, trip_id: TripId, photo_url: str) -> None:
        print(f"[СИСТЕМА] Фото самоката загружено: {photo_url}")

    def finish_ride(self, trip_id: TripId, scooter_id: ScooterId, battery_after: int) -> None:
        trip = self._get_trip(trip_id)
        scooter = self._get_scooter(scooter_id)
        now = self.clock.now()

        # Расчет стоимости
        duration = TimeRange(start=trip.started_at, end=now).duration_minutes()
        cost = self.tariff.price_per_minute * duration
        if cost.amount < self.tariff.minimum_cost.amount:
            cost = self.tariff.minimum_cost

        # Меняем состояние (обернули battery_after в BatteryLevel)
        trip.finish_ride(at=now, cost=cost)
        scooter.mark_returned(BatteryLevel(battery_after))

        self.trip_repo.save(trip)
        self.scooter_repo.save(scooter)

    def charge_payment(self, trip_id: TripId) -> None:
        trip = self._get_trip(trip_id)
        now = self.clock.now()

        if not trip.cost:
            raise ValueError("Стоимость не рассчитана")

        if self.payment_gateway.charge(trip.cost):
            trip.pay(at=now)
        else:
            trip.fail_payment(at=now)
            
        self.trip_repo.save(trip)

    def on_tick(self) -> None:
        now = self.clock.now()
        for trip in self.trip_repo.get_all():
            trip.on_expire_booking(now)
            self.trip_repo.save(trip)