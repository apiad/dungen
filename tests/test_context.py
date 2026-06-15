"""Tests for Context and ActionError."""

import pytest

from dungen.context import ActionError, Context
from dungen.entity import Entity
from dungen.graph import Graph
from dungen.ledger import Event
from dungen.world import World


@pytest.fixture()
def world():
    w = World()
    w.register(Entity("alice", hp=10))
    w.register(Entity("bob", hp=5))
    return w


@pytest.fixture()
def ctx(world):
    return Context(world, turn=3)


# ------------------------------------------------------------------
# Read interface
# ------------------------------------------------------------------


def test_turn(ctx):
    assert ctx.turn == 3


def test_graph_is_world_graph(ctx, world):
    assert ctx.graph is world.graph


def test_state_returns_dict_snapshot(ctx, world):
    snap = ctx.state("alice")
    assert isinstance(snap, dict)
    assert snap["hp"] == 10
    # Mutating the snapshot must not affect the live entity state.
    snap["hp"] = 999
    assert world.get("alice").state.get("hp") == 10


def test_inventory_returns_inventory_object(ctx, world):
    inv = ctx.inventory("alice")
    # Should be the same live Inventory object that world holds.
    assert inv is world.inventory("alice")


# ------------------------------------------------------------------
# Write interface
# ------------------------------------------------------------------


def test_set_state_mutates_entity(ctx, world):
    ctx.set_state("alice", "hp", 7)
    assert world.get("alice").state.get("hp") == 7


def test_add_item(ctx, world):
    ctx.add_item("alice", "sword")
    assert world.inventory("alice").contains("sword")


def test_remove_item_present(ctx, world):
    world.inventory("alice").add("potion")
    result = ctx.remove_item("alice", "potion")
    assert result is True
    assert not world.inventory("alice").contains("potion")


def test_remove_item_absent(ctx, world):
    result = ctx.remove_item("alice", "nonexistent")
    assert result is False


def test_transfer_item_success(ctx, world):
    world.inventory("alice").add("gold")
    result = ctx.transfer_item("gold", "alice", "bob")
    assert result is True
    assert not world.inventory("alice").contains("gold")
    assert world.inventory("bob").contains("gold")


def test_transfer_item_missing(ctx, world):
    result = ctx.transfer_item("gold", "alice", "bob")
    assert result is False


def test_log_appends_event(ctx, world):
    event = Event(
        turn=ctx.turn,
        actor_id="alice",
        action="test_action",
        args={},
        result={},
        perceived_by=["alice", "bob"],
    )
    ctx.log(event)
    all_events = world.ledger.export_all()
    assert len(all_events) == 1
    assert all_events[0] is event


# ------------------------------------------------------------------
# ActionError
# ------------------------------------------------------------------


def test_action_error_is_exception():
    with pytest.raises(ActionError):
        raise ActionError("not allowed")


def test_action_error_message():
    try:
        raise ActionError("insufficient funds")
    except ActionError as exc:
        assert str(exc) == "insufficient funds"
