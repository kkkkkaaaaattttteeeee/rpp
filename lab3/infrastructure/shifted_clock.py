from datetime import datetime, timedelta
from domain.exceptions import ClockMovedBack

class ShiftedClock:
    def __init__(self):
        self._offset = timedelta(0)

    def now(self) -> datetime:
        """Возвращает текущее системное время + сдвиг."""
        return datetime.now() + self._offset

    def move_to(self, moment: datetime) -> None:
        """Устанавливает сдвиг так, чтобы 'now()' вернул 'moment'."""
        current_real = datetime.now()
        if moment < current_real + self._offset:
            # Если пытаемся выставить время меньше текущего (с учетом сдвига)
            raise ClockMovedBack("Перевод часов назад запрещён")
        
        self._offset = moment - current_real