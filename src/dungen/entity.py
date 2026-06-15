"""Entity — the base class for all simulation participants."""

from __future__ import annotations

from dungen.state import State


class Entity:
    """Base class for all world entities.

    Users subclass Entity freely.  No inventory is built in; store
    Inventory objects in state only if they are JSON-serialisable
    (they are not — use World.inventory() instead).
    """

    id: str
    state: State

    def __init__(self, id: str, **initial_state) -> None:
        self.id = id
        self.state = State(initial_state)
