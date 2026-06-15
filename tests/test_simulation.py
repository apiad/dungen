"""Tests for events.py (SimEvent dataclasses) and simulation.py (Simulation)."""

from __future__ import annotations

import asyncio
from dataclasses import fields

import pytest

from dungen.engines import ActionCall, DeterministicEngine
from dungen.entity import Entity
from dungen.events import (
    ActionCommitted,
    AgentThinking,
    SimulationEnded,
    TurnResolved,
    TurnStarted,
)
from dungen.simulation import SeedError, Simulation
from dungen.world import World


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world_with_move():
    """Return (world, move_fn) with a committing 'move' action registered."""
    w = World()

    @w.action(commits=True)
    def move(actor_id: str, ctx, destination: str) -> str:
        """Move actor to destination."""
        ctx.set_state(actor_id, "location", destination)
        return destination

    return w, move


def _make_char(entity_id: str, engine=None, **state) -> Entity:
    char = Entity(entity_id, **state)
    if engine is not None:
        char.engine = engine
    return char


def _always_move(destination: str):
    """Return a DeterministicEngine that always calls move(destination=...)."""
    return DeterministicEngine(
        lambda char, perception: ActionCall("move", {"destination": destination})
    )


def _always_pass():
    return DeterministicEngine(lambda char, perception: ActionCall("pass"))


async def _collect(gen, limit=100):
    """Drain an async generator up to *limit* events and return the list."""
    events = []
    async for event in gen:
        events.append(event)
        if len(events) >= limit:
            break
    return events


# ---------------------------------------------------------------------------
# SimEvent dataclasses — structural tests
# ---------------------------------------------------------------------------


class TestSimEventDataclasses:
    def test_turn_started_is_dataclass(self):
        fs = {f.name for f in fields(TurnStarted)}
        assert fs == {"turn"}

    def test_turn_resolved_is_dataclass_with_committed_list(self):
        fs = {f.name for f in fields(TurnResolved)}
        assert "turn" in fs
        assert "committed" in fs

    def test_turn_resolved_default_committed_is_empty_list(self):
        tr = TurnResolved(turn=1)
        assert tr.committed == []

    def test_turn_resolved_committed_lists_are_independent(self):
        tr1 = TurnResolved(turn=1)
        tr2 = TurnResolved(turn=2)
        tr1.committed.append(object())
        assert tr2.committed == []

    def test_simulation_ended_stores_reason(self):
        se = SimulationEnded(reason="max_turns")
        assert se.reason == "max_turns"

    def test_action_committed_stores_fields(self):
        ac = ActionCommitted(
            turn=3, actor_id="hero", action="move", args={"destination": "north"}, result="north"
        )
        assert ac.turn == 3
        assert ac.actor_id == "hero"
        assert ac.action == "move"
        assert ac.args == {"destination": "north"}
        assert ac.result == "north"

    def test_agent_thinking_stores_turn_and_actor(self):
        at = AgentThinking(turn=2, actor_id="wizard")
        assert at.turn == 2
        assert at.actor_id == "wizard"


# ---------------------------------------------------------------------------
# Simulation — lockstep mode, basic event sequence
# ---------------------------------------------------------------------------


class TestSimulationLockstep:
    @pytest.mark.asyncio
    async def test_run_yields_turn_started_then_turn_resolved_then_ended(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass(), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=1))

        types = [type(e) for e in events]
        assert TurnStarted in types
        assert TurnResolved in types
        assert SimulationEnded in types

    @pytest.mark.asyncio
    async def test_run_turn_started_precedes_turn_resolved(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass(), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=1))

        started_idx = next(i for i, e in enumerate(events) if isinstance(e, TurnStarted))
        resolved_idx = next(i for i, e in enumerate(events) if isinstance(e, TurnResolved))
        assert started_idx < resolved_idx

    @pytest.mark.asyncio
    async def test_run_turn_resolved_has_correct_turn_number(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass(), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=2))

        resolved = [e for e in events if isinstance(e, TurnResolved)]
        assert [r.turn for r in resolved] == [1, 2]

    @pytest.mark.asyncio
    async def test_run_action_committed_appears_in_turn_resolved(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_move("forest"), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=1))

        resolved = next(e for e in events if isinstance(e, TurnResolved))
        assert len(resolved.committed) == 1
        ac = resolved.committed[0]
        assert ac.actor_id == "hero"
        assert ac.action == "move"
        assert ac.args == {"destination": "forest"}

    @pytest.mark.asyncio
    async def test_run_committed_action_mutates_world(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_move("dungeon"), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        await _collect(sim.run(max_turns=1))

        assert w.get("hero").state.get("location") == "dungeon"

    @pytest.mark.asyncio
    async def test_run_max_turns_terminates_with_reason(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=3))

        ended = next(e for e in events if isinstance(e, SimulationEnded))
        assert ended.reason == "max_turns"

    @pytest.mark.asyncio
    async def test_run_max_turns_produces_correct_number_of_turns(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=3))

        started = [e for e in events if isinstance(e, TurnStarted)]
        assert len(started) == 3

    @pytest.mark.asyncio
    async def test_run_pass_action_produces_empty_committed_list(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=1))

        resolved = next(e for e in events if isinstance(e, TurnResolved))
        assert resolved.committed == []

    @pytest.mark.asyncio
    async def test_run_multiple_characters_all_appear_in_agent_thinking(self):
        w, _ = _make_world_with_move()
        hero = _make_char("hero", engine=_always_pass(), location="a")
        goblin = _make_char("goblin", engine=_always_pass(), location="b")
        w.register(hero)
        w.register(goblin)

        sim = Simulation(w, [hero, goblin], turn_order="lockstep")
        events = await _collect(sim.run(max_turns=1))

        thinking = [e for e in events if isinstance(e, AgentThinking)]
        actor_ids = {e.actor_id for e in thinking}
        assert actor_ids == {"hero", "goblin"}

    @pytest.mark.asyncio
    async def test_run_no_agents_terminates_immediately(self):
        w = World()
        sim = Simulation(w, [], turn_order="lockstep")
        events = await _collect(sim.run())

        assert len(events) == 1
        assert isinstance(events[0], SimulationEnded)
        assert events[0].reason == "no_agents"


# ---------------------------------------------------------------------------
# Simulation — until condition
# ---------------------------------------------------------------------------


class TestSimulationUntilCondition:
    @pytest.mark.asyncio
    async def test_until_condition_terminates_when_true(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_move("goal"), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(
            sim.run(until=lambda snap: snap.state("hero").get("location") == "goal")
        )

        ended = next(e for e in events if isinstance(e, SimulationEnded))
        assert ended.reason == "until_condition"

    @pytest.mark.asyncio
    async def test_until_terminates_after_first_matching_turn(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_move("goal"), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(
            sim.run(until=lambda snap: snap.state("hero").get("location") == "goal")
        )

        started = [e for e in events if isinstance(e, TurnStarted)]
        # Condition is met after turn 1 (move applied), so exactly 1 turn runs.
        assert len(started) == 1

    @pytest.mark.asyncio
    async def test_until_false_does_not_terminate_prematurely(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass(), location="start")
        w.register(char)

        sim = Simulation(w, [char], turn_order="lockstep")
        events = await _collect(
            sim.run(
                max_turns=3,
                until=lambda snap: False,
            )
        )

        started = [e for e in events if isinstance(e, TurnStarted)]
        assert len(started) == 3

        ended = next(e for e in events if isinstance(e, SimulationEnded))
        assert ended.reason == "max_turns"


# ---------------------------------------------------------------------------
# Simulation.step()
# ---------------------------------------------------------------------------


class TestSimulationStep:
    @pytest.mark.asyncio
    async def test_step_returns_list(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char])
        result = await sim.step()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_step_first_event_is_turn_started(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char])
        events = await sim.step()
        assert isinstance(events[0], TurnStarted)

    @pytest.mark.asyncio
    async def test_step_advances_turn_counter(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char])
        events1 = await sim.step()
        events2 = await sim.step()

        assert events1[0].turn == 1
        assert events2[0].turn == 2

    @pytest.mark.asyncio
    async def test_step_contains_turn_resolved(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char])
        events = await sim.step()
        assert any(isinstance(e, TurnResolved) for e in events)

    @pytest.mark.asyncio
    async def test_step_with_commit_action_mutates_world(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_move("tower"), location="start")
        w.register(char)

        sim = Simulation(w, [char])
        await sim.step()

        assert w.get("hero").state.get("location") == "tower"

    @pytest.mark.asyncio
    async def test_step_does_not_yield_simulation_ended(self):
        """step() only runs one turn; it never emits SimulationEnded."""
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char])
        events = await sim.step()
        assert not any(isinstance(e, SimulationEnded) for e in events)


# ---------------------------------------------------------------------------
# Sequential mode — agents see prior commits
# ---------------------------------------------------------------------------


class TestSimulationSequential:
    @pytest.mark.asyncio
    async def test_sequential_second_agent_sees_first_commit(self):
        """In sequential mode, agent B perceives the world after agent A's commit."""
        w = World()

        @w.action(commits=True)
        def set_flag(actor_id: str, ctx, value: int) -> None:
            """Set flag state."""
            ctx.set_state("shared", "flag", value)

        # Agent A always sets flag=1.
        hero = _make_char("hero", engine=DeterministicEngine(
            lambda char, perception: ActionCall("set_flag", {"value": 1})
        ))
        hero.perceive_fn = lambda char, snap: snap.state("shared") if snap.has("shared") else {}

        # Track what agent B perceives.
        perceived = {}

        def observe_and_pass(char, perception):
            perceived["flag"] = perception.get("flag")
            return ActionCall("pass")

        shared_entity = Entity("shared", flag=0)
        w.register(shared_entity)
        w.register(hero)

        wizard = _make_char("wizard", engine=DeterministicEngine(observe_and_pass))
        wizard.perceive_fn = lambda char, snap: snap.state("shared") if snap.has("shared") else {}
        w.register(wizard)

        sim = Simulation(w, [hero, wizard], turn_order="sequential")
        events = await _collect(sim.run(max_turns=1))

        # Agent B should see flag=1 (set by agent A earlier in the same turn).
        assert perceived.get("flag") == 1

    @pytest.mark.asyncio
    async def test_sequential_turn_produces_one_turn_resolved(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", engine=_always_pass())
        w.register(char)

        sim = Simulation(w, [char], turn_order="sequential")
        events = await _collect(sim.run(max_turns=1))

        resolved = [e for e in events if isinstance(e, TurnResolved)]
        assert len(resolved) == 1

    @pytest.mark.asyncio
    async def test_sequential_committed_actions_collected_in_single_turn_resolved(self):
        w, _ = _make_world_with_move()
        hero = _make_char("hero", engine=_always_move("north"), location="start")
        goblin = _make_char("goblin", engine=_always_move("south"), location="start")
        w.register(hero)
        w.register(goblin)

        sim = Simulation(w, [hero, goblin], turn_order="sequential")
        events = await _collect(sim.run(max_turns=1))

        resolved = next(e for e in events if isinstance(e, TurnResolved))
        actor_ids = {ac.actor_id for ac in resolved.committed}
        assert actor_ids == {"hero", "goblin"}


# ---------------------------------------------------------------------------
# Simulation.seed()
# ---------------------------------------------------------------------------


class TestSimulationSeed:
    def test_seed_applies_action_to_world(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", location="start")
        w.register(char)

        sim = Simulation(w, [char])
        sim.seed(turn=0, actor_id="hero", action="move", args={"destination": "cave"})

        assert w.get("hero").state.get("location") == "cave"

    def test_seed_raises_seed_error_for_unknown_action(self):
        w = World()
        char = _make_char("hero")
        w.register(char)

        sim = Simulation(w, [char])
        with pytest.raises(SeedError, match="Unknown action"):
            sim.seed(turn=0, actor_id="hero", action="fly", args={})

    def test_seed_raises_seed_error_for_unknown_actor(self):
        w, _ = _make_world_with_move()
        sim = Simulation(w, [])

        with pytest.raises(SeedError, match="Unknown actor"):
            sim.seed(turn=0, actor_id="nobody", action="move", args={"destination": "x"})

    def test_seed_raises_seed_error_when_action_raises_action_error(self):
        from dungen.context import ActionError

        w = World()

        @w.action(commits=True)
        def guarded_move(actor_id: str, ctx, destination: str) -> None:
            """Move only to allowed places."""
            if destination == "forbidden":
                raise ActionError("You cannot go there.")
            ctx.set_state(actor_id, "location", destination)

        char = _make_char("hero", location="start")
        w.register(char)

        sim = Simulation(w, [char])
        with pytest.raises(SeedError, match="You cannot go there"):
            sim.seed(turn=0, actor_id="hero", action="guarded_move", args={"destination": "forbidden"})

    def test_seed_happy_path_does_not_raise(self):
        w, _ = _make_world_with_move()
        char = _make_char("hero", location="start")
        w.register(char)

        sim = Simulation(w, [char])
        # Should not raise.
        sim.seed(turn=0, actor_id="hero", action="move", args={"destination": "anywhere"})


# ---------------------------------------------------------------------------
# Simulation — perceive_fn
# ---------------------------------------------------------------------------


class TestSimulationPerceiveFn:
    @pytest.mark.asyncio
    async def test_perceive_fn_overrides_default_perception(self):
        w, _ = _make_world_with_move()
        perceived = {}

        def fn(char, perception):
            perceived["data"] = perception
            return ActionCall("pass")

        char = _make_char("hero", location="start")
        char.engine = DeterministicEngine(fn)
        char.perceive_fn = lambda c, snap: {"custom": True}
        w.register(char)

        sim = Simulation(w, [char])
        await _collect(sim.run(max_turns=1))

        assert perceived.get("data") == {"custom": True}

    @pytest.mark.asyncio
    async def test_no_perceive_fn_falls_back_to_entity_state(self):
        w, _ = _make_world_with_move()
        perceived = {}

        def fn(char, perception):
            perceived["data"] = perception
            return ActionCall("pass")

        char = _make_char("hero", location="start", hp=10)
        char.engine = DeterministicEngine(fn)
        w.register(char)

        sim = Simulation(w, [char])
        await _collect(sim.run(max_turns=1))

        assert perceived["data"].get("location") == "start"
        assert perceived["data"].get("hp") == 10
