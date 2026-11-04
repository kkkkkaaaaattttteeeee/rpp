from typing import Optional, Dict
from domain.aggregates import Scooter, Trip
from domain.value_objects import ScooterId, TripId
from domain.repositories import ScooterRepository, TripRepository

class InMemoryScooterRepository(ScooterRepository):
    def __init__(self):
        self._storage: Dict[str, Scooter] = {}

    def get(self, scooter_id: ScooterId) -> Optional[Scooter]:
        return self._storage.get(scooter_id.value)

    def save(self, scooter: Scooter) -> None:
        self._storage[scooter.id.value] = scooter

class InMemoryTripRepository(TripRepository):
    def __init__(self):
        self._storage: Dict[str, Trip] = {}

    def get(self, trip_id: TripId) -> Optional[Trip]:
        return self._storage.get(trip_id.value)

    def save(self, trip: Trip) -> None:
        self._storage[trip.id.value] = trip