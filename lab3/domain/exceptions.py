class DomainError(Exception):
    """Базовое исключение домена."""
    pass

class DomainInvariantViolation(DomainError):
    """Нарушение инварианта агрегата."""
    pass

class InvalidValueObject(DomainError):
    """Некорректное значение объекта-значения."""
    pass

class TransitionNotAllowed(DomainError):
    """Попытка выполнить недопустимое событие в текущем состоянии."""
    def __init__(self, state: str, event: str):
        super().__init__(f"Событие '{event}' недопустимо в состоянии '{state}'")
        self.state = state
        self.event = event