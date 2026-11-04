from datetime import datetime
from typing import Optional

from domain.aggregates import Scooter, Trip
from domain.value_objects import ScooterId, TripId, UserId, Money, Tariff, TimeRange
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
        user_repo, # UserRepository (заглушка)
        tariff: Tariff
    ):
        self.scooter_repo = scooter_repo
        self.trip_repo = trip_repo
        self.payment_gateway = payment_gateway
        self.clock = clock
        self.user_repo = user_repo
        self.tariff = tariff
        
        # Инициализируем предикаты для шлюзов
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

    # ЗАДАЧИ

    def book_scooter(self, trip_id: TripId, scooter_id: ScooterId, user_id: UserId) -> None:
        """Забронировать самокат (создание поездки в статусе Booked)"""
        now = self.clock.now()
        trip = Trip(
            id=trip_id, 
            scooter_id=scooter_id, 
            user_id=user_id, 
            created_at=now
        )
        self.trip_repo.save(trip)

    def start_ride(self, trip_id: TripId, scooter_id: ScooterId) -> None:
        """Начать поездку (включает авторизацию, разблокировку и старт)"""
        trip = self._get_trip(trip_id)
        scooter = self._get_scooter(scooter_id)
        now = self.clock.now()

        # 1. Проверка шлюзов (Долг и Авторизация)
        if not self.predicates.is_debt_free(trip.user_id):
            raise GatewayUnresolved("Есть задолженность")
            
        if not self.predicates.is_payment_authorized(Money(300)):
            raise GatewayUnresolved("Платёж не авторизован")

        # 2. Параллельное выполнение (последовательно в коде)
        # Сначала меняем состояние поездки, потом самоката.
        # Если что-то упадет - исключение не даст сохранить изменения.
        trip.start_ride(at=now)
        scooter.mark_rented()

        # 3. Сохраняем
        self.trip_repo.save(trip)
        self.scooter_repo.save(scooter)

    def pause_ride(self, trip_id: TripId) -> None:
        """Поставить на паузу"""
        trip = self._get_trip(trip_id)
        trip.pause_ride(at=self.clock.now())
        self.trip_repo.save(trip)

    def resume_ride(self, trip_id: TripId) -> None:
        """Возобновить поездку"""
        trip = self._get_trip(trip_id)
        trip.resume_ride(at=self.clock.now())
        self.trip_repo.save(trip)

    def upload_photo(self, trip_id: TripId, photo_url: str) -> None:
        """Человеческая задача: сфотографировать самокат. Принимает результат."""
        # В реальной системе здесь была бы проверка геозоны по фото.
        # Для нашей модели мы просто фиксируем действие.
        print(f"[СИСТЕМА] Фото самоката загружено: {photo_url}")

    def finish_ride(self, trip_id: TripId, scooter_id: ScooterId, battery_after: int) -> None:
        """Завершить поездку (включает расчет стоимости и возврат самоката)"""
        trip = self._get_trip(trip_id)
        scooter = self._get_scooter(scooter_id)
        now = self.clock.now()

        # Расчет стоимости
        duration = TimeRange(start=trip.started_at, end=now).duration_minutes()
        cost = self.tariff.price_per_minute * duration
        if cost.amount < self.tariff.minimum_cost.amount:
            cost = self.tariff.minimum_cost

        # Меняем состояние
        trip.finish_ride(at=now, cost=cost)
        scooter.mark_returned(battery_after)

        self.trip_repo.save(trip)
        self.scooter_repo.save(scooter)

    def charge_payment(self, trip_id: TripId) -> None:
        """Списать стоимость поездки"""
        trip = self._get_trip(trip_id)
        now = self.clock.now()

        if not trip.cost:
            raise ValueError("Стоимость не рассчитана")

        # Пытаемся списать
        if self.payment_gateway.charge(trip.cost):
            trip.pay(at=now)
        else:
            trip.fail_payment(at=now)
            
        self.trip_repo.save(trip)

    # ТАЙМЕРЫ

    def on_tick(self) -> None:
        """
        Служебный метод, вызываемый по POST /internal/tick.
        Проверяет все таймеры (истечение брони).
        """
        now = self.clock.now()
        # Получаем все поездки (метод добавлен в InMemory репозиторий)
        for trip in self.trip_repo.get_all():
            trip.on_expire_booking(now)
            self.trip_repo.save(trip)