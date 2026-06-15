from __future__ import annotations

from pydantic import BaseModel


class Event(BaseModel):
    turn: int
    actor_id: str
    action: str
    args: dict
    result: dict
    perceived_by: list[str]
    seeded: bool = False

    model_config = {"frozen": True}


class Ledger:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def query(self, **filters) -> list[Event]:
        results: list[Event] = []
        for event in self._events:
            match = True
            for field, value in filters.items():
                field_value = getattr(event, field)
                if isinstance(field_value, list):
                    if value not in field_value:
                        match = False
                        break
                else:
                    if field_value != value:
                        match = False
                        break
            if match:
                results.append(event)
        return results

    def export_pov(self, character_id: str) -> list[Event]:
        return self.query(perceived_by=character_id)

    def export_all(self) -> list[Event]:
        return list(self._events)
