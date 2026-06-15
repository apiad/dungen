"""World — the central simulation container."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

from dungen.entity import Entity
from dungen.graph import Graph
from dungen.inventory import Inventory
from dungen.ledger import Ledger


@dataclass
class ActionDef:
    name: str
    description: str
    commits: bool
    fn: Callable  # (actor_id: str, ctx: Context, **kwargs) -> None


class WorldSnapshot:
    """Read-only view of world state at a point in time.

    Constructed by World.snapshot().  Does NOT reference the live World.
    """

    def __init__(
        self,
        entities: list[Entity],
        state_map: dict[str, dict],
        graph: Graph,
    ) -> None:
        # Store frozen copies of entity objects (references only; we already
        # have their state captured in state_map).
        self._entities: list[Entity] = entities
        self._state_map: dict[str, dict] = state_map
        self.graph: Graph = graph

    def state(self, entity_id: str) -> dict:
        """Return the frozen state dict for *entity_id* at snapshot time."""
        return self._state_map[entity_id]

    def entities(self, type_=None) -> list[Entity]:
        """Return all entities, optionally filtered by *type_* (isinstance check)."""
        if type_ is None:
            return list(self._entities)
        return [e for e in self._entities if isinstance(e, type_)]

    def has(self, entity_id: str) -> bool:
        """Return True if *entity_id* existed at snapshot time."""
        return entity_id in self._state_map


class World:
    """Central container for the simulation: entities, graph, ledger, and actions."""

    graph: Graph
    ledger: Ledger

    def __init__(self) -> None:
        self.graph = Graph()
        self.ledger = Ledger()
        self._entities: dict[str, Entity] = {}
        self._actions: dict[str, ActionDef] = {}
        self._inventories: dict[str, Inventory] = {}

    # ------------------------------------------------------------------
    # Entity management
    # ------------------------------------------------------------------

    def register(self, entity: Entity) -> None:
        """Register *entity* with the world."""
        self._entities[entity.id] = entity

    def get(self, entity_id: str) -> Entity:
        """Return the entity for *entity_id*.

        Raises:
            KeyError: if no entity with that id has been registered.
        """
        return self._entities[entity_id]

    def list(self, type_=None) -> list[Entity]:
        """Return all registered entities, optionally filtered by *type_*."""
        if type_ is None:
            return list(self._entities.values())
        return [e for e in self._entities.values() if isinstance(e, type_)]

    # ------------------------------------------------------------------
    # Inventory management (separate from entity state)
    # ------------------------------------------------------------------

    def inventory(self, entity_id: str) -> Inventory:
        """Return the Inventory for *entity_id*, creating an empty one on first access."""
        if entity_id not in self._inventories:
            self._inventories[entity_id] = Inventory()
        return self._inventories[entity_id]

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> WorldSnapshot:
        """Return a frozen WorldSnapshot of the current world state."""
        entities = list(self._entities.values())
        state_map = {eid: e.state.snapshot() for eid, e in self._entities.items()}
        # Deep-copy the graph so the snapshot is truly independent.
        graph_copy = copy.deepcopy(self.graph)
        return WorldSnapshot(entities=entities, state_map=state_map, graph=graph_copy)

    # ------------------------------------------------------------------
    # Action registration
    # ------------------------------------------------------------------

    def action(self, commits: bool = True):
        """Parameterised decorator that registers an action function.

        Usage::

            @world.action(commits=True)
            def move(actor_id: str, ctx: Context, destination: str) -> None:
                ...

        The decorator returns the original function unchanged.
        """

        def decorator(fn: Callable) -> Callable:
            self._actions[fn.__name__] = ActionDef(
                name=fn.__name__,
                description=fn.__doc__ or "",
                commits=commits,
                fn=fn,
            )
            return fn

        return decorator
