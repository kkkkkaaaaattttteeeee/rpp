from typing import Protocol
from domain.value_objects import Money

class PaymentGateway(Protocol):
    """Порт для взаимодействия с платежной системой."""
    def authorize(self, amount: Money) -> bool: ...
    def charge(self, amount: Money) -> bool: ...

class InMemoryPaymentGateway(PaymentGateway):
    """Заглушка. Всегда одобряет авторизацию и списание (для тестов)."""
    def authorize(self, amount: Money) -> bool:
        return True
        
    def charge(self, amount: Money) -> bool:
        return True