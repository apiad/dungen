"""Context — controlled mutation interface passed to action functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dungen.graph import Graph
from dungen.inventory import Inventory
from dungen.ledger import Event

if TYPE_CHECKING:
    from dungen.world import World


class ActionError(Exception):
    """Raised inside an action function to reject the action."""


class Context:
    """Controlled mutation interface passed to action functions.

    Actions cannot mutate the World except through Context methods.
    """

    def __init__(self, world: "World", turn: int) -> None:
        self._world = world
        self._turn = turn

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @property
    def turn(self) -> int:
        """Return the current turn number."""
        return self._turn

    @property
    def graph(self) -> Graph:
        """Return the world's Graph (same object — read during action, do not mutate)."""
        return self._world.graph

    def state(self, entity_id: str) -> dict:
        """Return a read-only snapshot (deep copy) of the entity's state dict."""
        return self._world.get(entity_id).state.snapshot()

    def inventory(self, entity_id: str) -> Inventory:
        """Return the live Inventory for *entity_id*.

        Callers should treat this as read-only; use add_item / remove_item /
        transfer_item for mutations.
        """
        return self._world.inventory(entity_id)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def set_state(self, entity_id: str, key: str, value) -> None:
        """Set *key* = *value* on the entity's State."""
        self._world.get(entity_id).state.set(key, value)

    def add_item(self, entity_id: str, item_id: str) -> None:
        """Add one copy of *item_id* to *entity_id*'s inventory."""
        self._world.inventory(entity_id).add(item_id)

    def remove_item(self, entity_id: str, item_id: str) -> bool:
        """Remove one copy of *item_id* from *entity_id*'s inventory.

        Returns True if removed, False if not present.
        """
        return self._world.inventory(entity_id).remove(item_id)

    def transfer_item(
        self, item_id: str, from_entity_id: str, to_entity_id: str
    ) -> bool:
        """Move one copy of *item_id* from one entity's inventory to another's.

        Returns True on success, False if *item_id* was not in *from_entity_id*'s
        inventory.
        """
        return self._world.inventory(from_entity_id).transfer(
            item_id, self._world.inventory(to_entity_id)
        )

    def log(self, event: Event) -> None:
        """Append *event* to the world ledger.

        The caller is responsible for constructing the Event with the correct
        turn (available via ctx.turn).  Event is a frozen Pydantic model and
        cannot be mutated after construction.
        """
        self._world.ledger.append(event)
