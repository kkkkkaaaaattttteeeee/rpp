from domain.value_objects import UserId, Money
from domain.exceptions import GatewayUnresolved

class RentalPredicates:
    def __init__(self, user_repo, payment_gateway):
        self.user_repo = user_repo
        self.payment_gateway = payment_gateway

    def is_debt_free(self, user_id: UserId) -> bool:
        """Шлюз 1: Задолженность есть?"""
        return not self.user_repo.has_debt(user_id)

    def is_payment_authorized(self, amount: Money) -> bool:
        """Шлюз 2: Платеж выполнен (300 руб)?"""
        return self.payment_gateway.authorize(amount)

    def is_pause_needed(self, need_pause: bool) -> bool:
        """Шлюз 4: Нужна пауза?"""
        return need_pause

    def is_zone_allowed(self, is_allowed: bool) -> bool:
        """Шлюз 5: Разрешенная зона?"""
        return is_allowed

    def is_payment_charged(self, is_charged: bool) -> bool:
        """Шлюз 6: Прошло списание?"""
        return is_charged

    def is_ride_over_12_hours(self, duration_minutes: int) -> bool:
        """Шлюз 7: Поездка длилась больше 12 часов?"""
        return duration_minutes > (12 * 60)

    def resolve_zone_gateway(self, is_allowed_zone: bool, is_default: bool = False) -> bool:
        if is_allowed_zone: return True
        if is_default: return False
        raise GatewayUnresolved("Разрешённая зона?")
