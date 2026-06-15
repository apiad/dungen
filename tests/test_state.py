"""Tests for State key-value store."""

import pytest

from dungen.state import State


# ---------------------------------------------------------------------------
# Basic operations
# ---------------------------------------------------------------------------


def test_set_and_get():
    s = State()
    s.set("hp", 100)
    assert s.get("hp") == 100


def test_has_present():
    s = State()
    s.set("name", "hero")
    assert s.has("name") is True


def test_has_absent():
    s = State()
    assert s.has("missing") is False


def test_keys_empty():
    s = State()
    assert s.keys() == []


def test_keys_populated():
    s = State()
    s.set("a", 1)
    s.set("b", 2)
    assert sorted(s.keys()) == ["a", "b"]


# ---------------------------------------------------------------------------
# Default value on get
# ---------------------------------------------------------------------------


def test_get_default_when_absent():
    s = State()
    assert s.get("x") is None


def test_get_custom_default_when_absent():
    s = State()
    assert s.get("x", 42) == 42


def test_get_does_not_use_default_when_present():
    s = State()
    s.set("x", 0)
    assert s.get("x", 99) == 0


# ---------------------------------------------------------------------------
# Constructor with initial dict
# ---------------------------------------------------------------------------


def test_constructor_initial_dict():
    s = State({"a": 1, "b": [1, 2, 3]})
    assert s.get("a") == 1
    assert s.get("b") == [1, 2, 3]


def test_constructor_none():
    s = State(None)
    assert s.keys() == []


def test_constructor_initial_dict_non_serializable_raises():
    with pytest.raises(TypeError):
        State({"bad": object()})


# ---------------------------------------------------------------------------
# Snapshot (deep copy)
# ---------------------------------------------------------------------------


def test_snapshot_returns_dict():
    s = State({"x": 10})
    snap = s.snapshot()
    assert isinstance(snap, dict)
    assert snap["x"] == 10


def test_snapshot_mutation_does_not_affect_state():
    s = State({"items": [1, 2, 3]})
    snap = s.snapshot()
    snap["items"].append(99)
    # Internal state must be unchanged
    assert s.get("items") == [1, 2, 3]


def test_snapshot_reflects_current_values():
    s = State({"v": 1})
    s.set("v", 2)
    assert s.snapshot()["v"] == 2


# ---------------------------------------------------------------------------
# JSON-serializable constraint
# ---------------------------------------------------------------------------


def test_set_non_serializable_raises_type_error():
    s = State()
    with pytest.raises(TypeError):
        s.set("x", object())


def test_set_non_serializable_set_not_defined():
    """Failed set must not store anything."""
    s = State()
    with pytest.raises(TypeError):
        s.set("x", object())
    assert not s.has("x")


def test_set_supports_json_types():
    s = State()
    s.set("null", None)
    s.set("bool", True)
    s.set("int", 42)
    s.set("float", 3.14)
    s.set("str", "hello")
    s.set("list", [1, "a", None])
    s.set("dict", {"nested": True})
    assert s.get("null") is None
    assert s.get("bool") is True
    assert s.get("int") == 42
