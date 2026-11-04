from domain.value_objects import UserId, Money
from domain.exceptions import GatewayUnresolved

class RentalPredicates:
    def __init__(self, user_repo, payment_gateway):
        self.user_repo = user_repo
        self.payment_gateway = payment_gateway

    def is_debt_free(self, user_id: UserId) -> bool:
        return not self.user_repo.has_debt(user_id)

    def is_payment_authorized(self, amount: Money) -> bool:
        return self.payment_gateway.authorize(amount)

    # Пример шлюза с ошибкой (если нет потока по умолчанию)
    def resolve_zone_gateway(self, is_allowed_zone: bool, is_default: bool = False) -> bool:
        if is_allowed_zone:
            return True
        if is_default:
            return False
        raise GatewayUnresolved("Разрешённая зона?")