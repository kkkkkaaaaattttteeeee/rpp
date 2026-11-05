import os
import logging
from datetime import datetime
from dataclasses import asdict

from flask import Flask, request, jsonify

# Импорты доменного слоя
from domain.value_objects import TripId, ScooterId, UserId, Money, Tariff
from domain.exceptions import (
    DomainError, DomainInvariantViolation, InvalidValueObject,
    TransitionNotAllowed, GatewayUnresolved, ClockMovedBack
)

# Импорты прикладного слоя 
from application.rental_process import RentalProcess

# Импорты инфраструктурного слоя 
from infrastructure.repositories import (
    InMemoryScooterRepository, InMemoryTripRepository
)
from infrastructure.payment_gateway import InMemoryPaymentGateway
from infrastructure.shifted_clock import ShiftedClock


# Настройка логирования через переменные окружения
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# Инициализация Flask-приложения
app = Flask(__name__)


# Заглушка репозитория пользователей
class UserRepo:
    def has_debt(self, user_id: UserId) -> bool:
        return False


# Создаем всё ОДИН раз при запуске приложения 
scooter_repo = InMemoryScooterRepository()
trip_repo = InMemoryTripRepository()
payment_gw = InMemoryPaymentGateway()
clock = ShiftedClock()
user_repo = UserRepo()

# Тариф: 5 руб/мин, минимум 50 руб
tariff = Tariff(price_per_minute=Money(5.0), minimum_cost=Money(50.0))

# Прикладной сервис процесса
process = RentalProcess(
    scooter_repo=scooter_repo,
    trip_repo=trip_repo,
    payment_gateway=payment_gw,
    clock=clock,
    user_repo=user_repo,
    tariff=tariff
)


# Общий обработчик доменных исключений
@app.errorhandler(DomainError)
def handle_domain_error(e):
    logger.warning(f"Доменная ошибка: {type(e).__name__} - {e}")

    if isinstance(e, TransitionNotAllowed):
        return jsonify({
            "error": "transition_not_allowed",
            "message": str(e)
        }), 409

    if isinstance(e, (DomainInvariantViolation, InvalidValueObject, ClockMovedBack)):
        return jsonify({
            "error": "unprocessable_entity",
            "message": str(e)
        }), 422

    if isinstance(e, GatewayUnresolved):
        return jsonify({
            "error": "gateway_unresolved",
            "message": str(e)
        }), 500

    return jsonify({
        "error": "domain_error",
        "message": str(e)
    }), 500


# Обработка ошибки "Не найдено"
@app.errorhandler(ValueError)
def handle_value_error(e):
    logger.warning(f"Не найдено: {e}")
    return jsonify({
        "error": "not_found",
        "message": str(e)
    }), 404


# Маршрут проверки готовности (для Docker healthcheck)
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200


#  Бизнес-маршруты 

@app.route("/rentals/<trip_id>/book", methods=["POST"])
def book_trip(trip_id):
    data = request.get_json() or {}
    scooter_id = data.get("scooter_id")
    user_id = data.get("user_id")

    if not scooter_id or not user_id:
        return jsonify({
            "error": "bad_request",
            "message": "scooter_id и user_id обязательны"
        }), 400

    process.book_scooter(
        TripId(trip_id),
        ScooterId(scooter_id),
        UserId(user_id)
    )
    return jsonify({"status": "ok", "trip_id": trip_id}), 200


@app.route("/rentals/<trip_id>/start", methods=["POST"])
def start_ride(trip_id):
    data = request.get_json() or {}
    scooter_id = data.get("scooter_id")

    if not scooter_id:
        return jsonify({
            "error": "bad_request",
            "message": "scooter_id обязателен"
        }), 400

    process.start_ride(TripId(trip_id), ScooterId(scooter_id))
    return jsonify({"status": "ok"}), 200


@app.route("/rentals/<trip_id>/pause", methods=["POST"])
def pause_ride(trip_id):
    process.pause_ride(TripId(trip_id))
    return jsonify({"status": "ok"}), 200


@app.route("/rentals/<trip_id>/resume", methods=["POST"])
def resume_ride(trip_id):
    process.resume_ride(TripId(trip_id))
    return jsonify({"status": "ok"}), 200


@app.route("/rentals/<trip_id>/upload-photo", methods=["POST"])
def upload_photo(trip_id):
    data = request.get_json() or {}
    photo_url = data.get("photo_url")

    if not photo_url:
        return jsonify({
            "error": "bad_request",
            "message": "photo_url обязателен"
        }), 400

    process.upload_photo(TripId(trip_id), photo_url)
    return jsonify({"status": "ok"}), 200


@app.route("/rentals/<trip_id>/finish", methods=["POST"])
def finish_ride(trip_id):
    data = request.get_json() or {}
    scooter_id = data.get("scooter_id")
    battery_after = data.get("battery_after", 100)

    if not scooter_id:
        return jsonify({
            "error": "bad_request",
            "message": "scooter_id обязателен"
        }), 400

    process.finish_ride(
        TripId(trip_id),
        ScooterId(scooter_id),
        battery_after
    )
    return jsonify({"status": "ok"}), 200


@app.route("/rentals/<trip_id>/pay", methods=["POST"])
def pay(trip_id):
    process.charge_payment(TripId(trip_id))
    return jsonify({"status": "ok"}), 200


# Получение состояния, событий и допустимых действий 
@app.route("/rentals/<trip_id>", methods=["GET"])
def get_trip(trip_id):
    trip = trip_repo.get(TripId(trip_id))
    if not trip:
        raise ValueError(f"Поездка {trip_id} не найдена")

    # Сериализация доменных событий
    events_data = [asdict(event) for event in trip.events]

    return jsonify({
        "id": trip.id.value,
        "status": trip.status,
        "allowed_events": list(trip.allowed_events),
        "events": events_data
    }), 200


# Служебный маршрут прокрутки времени
@app.route("/internal/tick", methods=["POST"])
def tick():
    data = request.get_json() or {}
    now_str = data.get("now")

    if now_str:
        try:
            moment = datetime.fromisoformat(now_str)
        except ValueError:
            return jsonify({
                "error": "bad_request",
                "message": "Неверный формат времени. Используйте ISO 8601."
            }), 400
        clock.move_to(moment)

    process.on_tick()
    return jsonify({
        "status": "ticked",
        "now": clock.now().isoformat()
    }), 200


# Запуск приложения
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)