"""Simulation — orchestrates turns, agents, and world mutations."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncGenerator, Callable

from dungen.events import (
    ActionCommitted,
    AgentThinking,
    SimulationEnded,
    SimEvent,
    TurnResolved,
    TurnStarted,
)

if TYPE_CHECKING:
    from dungen.entity import Entity
    from dungen.world import World, WorldSnapshot


class SeedError(Exception):
    """Raised by Simulation.seed() when a pre-determined event cannot be applied."""


class Simulation:
    """Orchestrates turns, agent decisions, and world mutations.

    Parameters
    ----------
    world:
        The World instance that holds entities, graph, and action registry.
    characters:
        Entities that participate as decision-making agents.  Each must have
        an ``.engine`` attribute (Engine instance); may optionally have a
        ``.perceive_fn(character, snapshot) -> dict`` attribute.
    turn_order:
        ``"lockstep"`` — all agents decide in parallel, commits resolve
        simultaneously.  ``"sequential"`` — each agent decides and commits
        in order, seeing prior commits within the same turn.
    """

    def __init__(
        self,
        world: "World",
        characters: list["Entity"],
        turn_order: str = "lockstep",
    ) -> None:
        self._world = world
        self._characters = characters
        self._turn_order = turn_order
        self._turn = 0

        # Bind AgentEngine instances so they can construct Context for read tools.
        from dungen.engines import AgentEngine

        for char in characters:
            engine = getattr(char, "engine", None)
            if isinstance(engine, AgentEngine):
                engine.bind(world._actions, world)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        max_turns: int | None = None,
        until: Callable[["WorldSnapshot"], bool] | None = None,
    ) -> AsyncGenerator[SimEvent, None]:
        """Async generator that yields SimEvents as the simulation runs.

        Termination (in priority order):
        1. ``max_turns`` exceeded.
        2. No characters remain.
        3. ``until`` predicate becomes True (checked after each turn resolves).
        """
        while True:
            self._turn += 1

            if max_turns is not None and self._turn > max_turns:
                yield SimulationEnded(reason="max_turns")
                return

            if not self._characters:
                yield SimulationEnded(reason="no_agents")
                return

            yield TurnStarted(turn=self._turn)

            if self._turn_order == "lockstep":
                async for event in self._run_lockstep_turn():
                    yield event
            else:
                async for event in self._run_sequential_turn():
                    yield event

            if until is not None and until(self._world.snapshot()):
                yield SimulationEnded(reason="until_condition")
                return

    async def step(self) -> list[SimEvent]:
        """Advance one turn and return all SimEvents from that turn as a list."""
        self._turn += 1
        events: list[SimEvent] = [TurnStarted(turn=self._turn)]

        if self._turn_order == "lockstep":
            async for event in self._run_lockstep_turn():
                events.append(event)
        else:
            async for event in self._run_sequential_turn():
                events.append(event)

        return events

    def seed(self, turn: int, actor_id: str, action: str, args: dict) -> None:
        """Apply a pre-determined action, bypassing agent decision.

        Validates by actually running the action fn through a Context.
        Raises SeedError if the action is unknown, the actor is unknown,
        or the action fn raises ActionError.
        """
        action_def = self._world._actions.get(action)
        if action_def is None:
            raise SeedError(f"Unknown action: {action!r}")

        entity = self._world._entities.get(actor_id)
        if entity is None:
            raise SeedError(f"Unknown actor: {actor_id!r}")

        from dungen.context import ActionError, Context

        ctx = Context(self._world, turn)
        try:
            result = action_def.fn(actor_id=actor_id, ctx=ctx, **args)
            if asyncio.iscoroutine(result):
                asyncio.get_event_loop().run_until_complete(result)
        except ActionError as e:
            raise SeedError(str(e)) from e

    # ------------------------------------------------------------------
    # Internal turn runners (async generators)
    # ------------------------------------------------------------------

    async def _run_lockstep_turn(self) -> AsyncGenerator[SimEvent, None]:
        """All agents decide in parallel; commits resolve simultaneously."""
        snapshot = self._world.snapshot()

        for char in self._characters:
            yield AgentThinking(turn=self._turn, actor_id=char.id)

        results = await asyncio.gather(
            *[self._decide_one(char, snapshot) for char in self._characters]
        )

        from dungen.context import ActionError, Context

        ctx = Context(self._world, self._turn)
        committed: list[ActionCommitted] = []

        for char, action_call in zip(self._characters, results):
            if action_call.action == "pass":
                continue
            action_def = self._world._actions.get(action_call.action)
            if action_def is None or not action_def.commits:
                continue
            try:
                result = action_def.fn(actor_id=char.id, ctx=ctx, **action_call.args)
                if asyncio.iscoroutine(result):
                    result = await result
            except ActionError:
                result = None
            committed.append(
                ActionCommitted(
                    turn=self._turn,
                    actor_id=char.id,
                    action=action_call.action,
                    args=action_call.args,
                    result=result,
                )
            )

        yield TurnResolved(turn=self._turn, committed=committed)

    async def _run_sequential_turn(self) -> AsyncGenerator[SimEvent, None]:
        """Each agent decides and commits in order, seeing prior commits."""
        from dungen.context import ActionError, Context

        committed: list[ActionCommitted] = []

        for char in self._characters:
            yield AgentThinking(turn=self._turn, actor_id=char.id)

            snapshot = self._world.snapshot()
            action_call = await self._decide_one(char, snapshot)

            if action_call.action == "pass":
                continue

            action_def = self._world._actions.get(action_call.action)
            if action_def is None or not action_def.commits:
                continue

            ctx = Context(self._world, self._turn)
            try:
                result = action_def.fn(actor_id=char.id, ctx=ctx, **action_call.args)
                if asyncio.iscoroutine(result):
                    result = await result
            except ActionError:
                result = None

            committed.append(
                ActionCommitted(
                    turn=self._turn,
                    actor_id=char.id,
                    action=action_call.action,
                    args=action_call.args,
                    result=result,
                )
            )

        yield TurnResolved(turn=self._turn, committed=committed)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _decide_one(self, char: "Entity", snapshot: "WorldSnapshot"):
        """Ask one character's engine for an ActionCall."""
        from dungen.engines import ActionCall

        perceive_fn = getattr(char, "perceive_fn", None)
        if perceive_fn is not None:
            perception = perceive_fn(char, snapshot)
        else:
            perception = snapshot.state(char.id) if snapshot.has(char.id) else {}

        engine = getattr(char, "engine", None)
        if engine is None:
            return ActionCall("pass", {})

        return await engine.decide(char, perception, snapshot, self._turn)
