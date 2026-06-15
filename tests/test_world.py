"""Tests for Entity, World, ActionDef, and WorldSnapshot."""

import pytest

from dungen.entity import Entity
from dungen.inventory import Inventory
from dungen.world import ActionDef, World, WorldSnapshot


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


def test_entity_init_sets_id():
    e = Entity("hero")
    assert e.id == "hero"


def test_entity_init_kwargs_stored_in_state():
    e = Entity("hero", hp=100, name="Aria")
    assert e.state.get("hp") == 100
    assert e.state.get("name") == "Aria"


def test_entity_init_no_kwargs_empty_state():
    e = Entity("npc")
    assert e.state.keys() == []


# ---------------------------------------------------------------------------
# World.register / get / list
# ---------------------------------------------------------------------------


def test_world_register_and_get():
    w = World()
    e = Entity("hero", hp=50)
    w.register(e)
    assert w.get("hero") is e


def test_world_get_missing_raises_key_error():
    w = World()
    with pytest.raises(KeyError):
        w.get("nobody")


def test_world_list_all():
    w = World()
    a = Entity("a")
    b = Entity("b")
    w.register(a)
    w.register(b)
    result = w.list()
    assert set(e.id for e in result) == {"a", "b"}


def test_world_list_empty():
    w = World()
    assert w.list() == []


# ---------------------------------------------------------------------------
# World.list(type_) — subclass filtering
# ---------------------------------------------------------------------------


class Monster(Entity):
    pass


class Hero(Entity):
    pass


def test_world_list_filters_by_type():
    w = World()
    h = Hero("hero")
    m1 = Monster("goblin")
    m2 = Monster("orc")
    w.register(h)
    w.register(m1)
    w.register(m2)

    monsters = w.list(Monster)
    assert len(monsters) == 2
    assert all(isinstance(e, Monster) for e in monsters)

    heroes = w.list(Hero)
    assert len(heroes) == 1
    assert heroes[0].id == "hero"


def test_world_list_type_no_match_returns_empty():
    w = World()
    w.register(Entity("plain"))
    assert w.list(Monster) == []


# ---------------------------------------------------------------------------
# World.inventory
# ---------------------------------------------------------------------------


def test_world_inventory_returns_inventory_instance():
    w = World()
    inv = w.inventory("hero")
    assert isinstance(inv, Inventory)


def test_world_inventory_same_object_on_repeated_calls():
    w = World()
    inv1 = w.inventory("hero")
    inv2 = w.inventory("hero")
    assert inv1 is inv2


def test_world_inventory_different_entities_different_objects():
    w = World()
    assert w.inventory("a") is not w.inventory("b")


# ---------------------------------------------------------------------------
# World.action decorator
# ---------------------------------------------------------------------------


def test_action_decorator_returns_original_function():
    w = World()

    @w.action(commits=True)
    def move(actor_id: str, destination: str) -> None:
        """Move actor to destination."""

    # The decorator must return the unwrapped function.
    assert move.__name__ == "move"
    assert callable(move)


def test_action_decorator_registers_action_def():
    w = World()

    @w.action(commits=False)
    def look(actor_id: str) -> None:
        """Look around."""

    assert "look" in w._actions
    defn = w._actions["look"]
    assert isinstance(defn, ActionDef)
    assert defn.name == "look"
    assert defn.commits is False
    assert defn.fn is look


def test_action_decorator_commits_flag_true():
    w = World()

    @w.action(commits=True)
    def attack(actor_id: str, target_id: str) -> None:
        pass

    assert w._actions["attack"].commits is True


# ---------------------------------------------------------------------------
# World.snapshot → WorldSnapshot
# ---------------------------------------------------------------------------


def test_snapshot_returns_world_snapshot_instance():
    w = World()
    snap = w.snapshot()
    assert isinstance(snap, WorldSnapshot)


def test_snapshot_has_returns_true_for_registered():
    w = World()
    w.register(Entity("hero"))
    snap = w.snapshot()
    assert snap.has("hero") is True


def test_snapshot_has_returns_false_for_absent():
    w = World()
    snap = w.snapshot()
    assert snap.has("ghost") is False


def test_snapshot_state_returns_dict():
    w = World()
    w.register(Entity("hero", hp=42))
    snap = w.snapshot()
    s = snap.state("hero")
    assert isinstance(s, dict)
    assert s["hp"] == 42


def test_snapshot_state_is_frozen_not_live():
    """Mutating entity state after snapshot must not affect the snapshot."""
    w = World()
    e = Entity("hero", hp=100)
    w.register(e)
    snap = w.snapshot()
    e.state.set("hp", 1)  # mutate live entity
    assert snap.state("hero")["hp"] == 100  # snapshot is unchanged


def test_snapshot_entities_all():
    w = World()
    w.register(Entity("a"))
    w.register(Entity("b"))
    snap = w.snapshot()
    ids = {e.id for e in snap.entities()}
    assert ids == {"a", "b"}


def test_snapshot_entities_filtered_by_type():
    w = World()
    w.register(Hero("h"))
    w.register(Monster("m1"))
    w.register(Monster("m2"))
    snap = w.snapshot()
    assert len(snap.entities(Monster)) == 2
    assert len(snap.entities(Hero)) == 1


def test_snapshot_graph_is_independent():
    """Mutating the live graph after snapshot must not affect snapshot.graph."""
    w = World()
    w.graph.add_node("room1")
    snap = w.snapshot()
    w.graph.add_node("room2")
    assert "room2" not in snap.graph._nodes
