"""Tests for engines.py — DeterministicEngine, HumanEngine, AgentEngine hooks."""

from __future__ import annotations

import asyncio
import pytest

from dungen.engines import ActionCall, DeterministicEngine, HumanEngine, AgentEngine
from dungen.entity import Entity
from dungen.world import World, WorldSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot() -> WorldSnapshot:
    """Return a minimal WorldSnapshot for use in tests."""
    w = World()
    return w.snapshot()


def _make_character(entity_id: str = "hero") -> Entity:
    return Entity(entity_id, hp=10)


# ---------------------------------------------------------------------------
# ActionCall
# ---------------------------------------------------------------------------


def test_action_call_stores_action_and_args():
    call = ActionCall(action="move", args={"destination": "north"})
    assert call.action == "move"
    assert call.args == {"destination": "north"}


def test_action_call_default_args_empty_dict():
    call = ActionCall(action="pass")
    assert call.args == {}


def test_action_call_is_dataclass():
    from dataclasses import fields
    fs = {f.name for f in fields(ActionCall)}
    assert "action" in fs
    assert "args" in fs


# ---------------------------------------------------------------------------
# DeterministicEngine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_engine_returns_fn_result():
    expected = ActionCall(action="attack", args={"target": "goblin"})

    def fn(character, perception):
        return expected

    engine = DeterministicEngine(fn)
    result = await engine.decide(_make_character(), {}, _make_snapshot())
    assert result is expected


@pytest.mark.asyncio
async def test_deterministic_engine_passes_character_and_perception():
    received = {}

    def fn(character, perception):
        received["character"] = character
        received["perception"] = perception
        return ActionCall("pass")

    char = _make_character("warrior")
    perception = {"enemies": ["goblin"], "hp": 10}

    engine = DeterministicEngine(fn)
    await engine.decide(char, perception, _make_snapshot())

    assert received["character"] is char
    assert received["perception"] == perception


@pytest.mark.asyncio
async def test_deterministic_engine_world_not_passed_to_fn():
    """DeterministicEngine fn only receives character + perception (not world)."""
    call_args = []

    def fn(character, perception):
        call_args.append((character, perception))
        return ActionCall("pass")

    engine = DeterministicEngine(fn)
    snap = _make_snapshot()
    await engine.decide(_make_character(), {"x": 1}, snap)

    assert len(call_args) == 1
    char, perc = call_args[0]
    # No world in args — fn signature is (character, perception)
    assert perc == {"x": 1}


# ---------------------------------------------------------------------------
# HumanEngine — sync input_fn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_human_engine_sync_input_fn():
    expected = ActionCall(action="look", args={})

    def sync_input(character, perception):
        return expected

    engine = HumanEngine(input_fn=sync_input)
    result = await engine.decide(_make_character(), {}, _make_snapshot())
    assert result is expected


@pytest.mark.asyncio
async def test_human_engine_sync_input_fn_receives_character_and_perception():
    received = {}

    def sync_input(character, perception):
        received["character"] = character
        received["perception"] = perception
        return ActionCall("pass")

    char = _make_character("thief")
    perc = {"items": ["key"]}

    engine = HumanEngine(input_fn=sync_input)
    await engine.decide(char, perc, _make_snapshot())

    assert received["character"] is char
    assert received["perception"] == perc


# ---------------------------------------------------------------------------
# HumanEngine — async input_fn
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_human_engine_async_input_fn():
    expected = ActionCall(action="flee", args={"direction": "south"})

    async def async_input(character, perception):
        return expected

    engine = HumanEngine(input_fn=async_input)
    result = await engine.decide(_make_character(), {}, _make_snapshot())
    assert result is expected


@pytest.mark.asyncio
async def test_human_engine_async_input_fn_is_awaited():
    awaited = {"done": False}

    async def async_input(character, perception):
        awaited["done"] = True
        return ActionCall("pass")

    engine = HumanEngine(input_fn=async_input)
    await engine.decide(_make_character(), {}, _make_snapshot())
    assert awaited["done"] is True


# ---------------------------------------------------------------------------
# AgentEngine — hook registration and _run_hooks
# ---------------------------------------------------------------------------


def _make_minimal_agent_engine():
    """Return an AgentEngine with a stub LLM (never called in hook tests)."""
    # We pass None as LLM — hooks tests don't call decide(), so it's fine.
    engine = AgentEngine.__new__(AgentEngine)
    engine._llm = None
    engine._system_prompt = "You are an agent."
    engine._hooks = {
        "before_turn": [],
        "after_read_action": [],
        "after_turn": [],
        "on_checkpoint": [],
    }
    engine._messages = []
    engine._action_tools = []
    engine._read_tools = []
    engine._commit_tools = []
    return engine


def test_agent_engine_on_registers_hook():
    engine = _make_minimal_agent_engine()

    @engine.on("before_turn")
    async def my_hook(character, messages, world):
        pass

    assert my_hook in engine._hooks["before_turn"]


def test_agent_engine_on_unknown_event_raises():
    engine = _make_minimal_agent_engine()

    with pytest.raises(ValueError, match="Unknown hook event"):
        @engine.on("nonexistent_event")
        async def bad_hook(character, messages, world):
            pass


def test_agent_engine_on_returns_original_function():
    engine = _make_minimal_agent_engine()

    async def my_hook(character, messages, world):
        return None

    result = engine.on("after_turn")(my_hook)
    assert result is my_hook


@pytest.mark.asyncio
async def test_agent_engine_run_hooks_fires_hook():
    engine = _make_minimal_agent_engine()
    fired = {"count": 0}

    @engine.on("before_turn")
    async def counting_hook(character, messages, world):
        fired["count"] += 1

    snap = _make_snapshot()
    char = _make_character()
    await engine._run_hooks("before_turn", char, snap)

    assert fired["count"] == 1


@pytest.mark.asyncio
async def test_agent_engine_run_hooks_passes_messages():
    engine = _make_minimal_agent_engine()
    engine._messages = ["msg1", "msg2"]  # type: ignore[list-item]
    received = {}

    @engine.on("after_turn")
    async def capture_hook(character, messages, world):
        received["messages"] = list(messages)

    snap = _make_snapshot()
    await engine._run_hooks("after_turn", _make_character(), snap)

    assert received["messages"] == ["msg1", "msg2"]


@pytest.mark.asyncio
async def test_agent_engine_hook_returning_list_replaces_messages():
    engine = _make_minimal_agent_engine()
    engine._messages = ["old_msg"]  # type: ignore[list-item]
    new_msgs = ["new_msg_1", "new_msg_2"]

    @engine.on("before_turn")
    async def replacing_hook(character, messages, world):
        return new_msgs

    snap = _make_snapshot()
    await engine._run_hooks("before_turn", _make_character(), snap)

    assert engine._messages is new_msgs


@pytest.mark.asyncio
async def test_agent_engine_hook_returning_none_preserves_messages():
    engine = _make_minimal_agent_engine()
    original = ["keep_me"]
    engine._messages = original  # type: ignore[list-item]

    @engine.on("after_turn")
    async def noop_hook(character, messages, world):
        return None  # explicit None — messages must not change

    snap = _make_snapshot()
    await engine._run_hooks("after_turn", _make_character(), snap)

    assert engine._messages is original


@pytest.mark.asyncio
async def test_agent_engine_multiple_hooks_run_in_order():
    engine = _make_minimal_agent_engine()
    order = []

    @engine.on("after_read_action")
    async def hook_a(character, messages, world, **kwargs):
        order.append("a")

    @engine.on("after_read_action")
    async def hook_b(character, messages, world, **kwargs):
        order.append("b")

    snap = _make_snapshot()
    await engine._run_hooks("after_read_action", _make_character(), snap)

    assert order == ["a", "b"]


@pytest.mark.asyncio
async def test_agent_engine_on_checkpoint_receives_name_kwarg():
    engine = _make_minimal_agent_engine()
    received = {}

    @engine.on("on_checkpoint")
    async def checkpoint_hook(character, messages, world, **kwargs):
        received["name"] = kwargs.get("name")

    snap = _make_snapshot()
    await engine._run_hooks("on_checkpoint", _make_character(), snap, name="mid_game")

    assert received["name"] == "mid_game"


# ---------------------------------------------------------------------------
# AgentEngine — bind()
# ---------------------------------------------------------------------------


def test_agent_engine_bind_splits_into_read_and_commit():
    engine = _make_minimal_agent_engine()

    w = World()

    @w.action(commits=False)
    def look(actor_id: str, ctx, direction: str) -> str:
        """Look in a direction."""
        return "you see nothing"

    @w.action(commits=True)
    def move(actor_id: str, ctx, destination: str) -> None:
        """Move to destination."""

    engine.bind(w._actions)

    assert len(engine._read_tools) == 1
    assert len(engine._commit_tools) == 1
    assert engine._read_tools[0].name == "look"
    assert engine._commit_tools[0].name == "move"


def test_agent_engine_bind_tool_parameters_exclude_framework_params():
    engine = _make_minimal_agent_engine()

    w = World()

    @w.action(commits=True)
    def attack(actor_id: str, ctx, target: str, damage: int) -> None:
        """Attack a target."""

    engine.bind(w._actions)

    tool = engine._commit_tools[0]
    params = tool.parameters()
    assert "actor_id" not in params
    assert "ctx" not in params
    assert "target" in params
    assert "damage" in params
