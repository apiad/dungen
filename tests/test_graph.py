"""Tests for the Graph primitive."""

import pytest

from dungen.graph import Graph


# ---------------------------------------------------------------------------
# add_node
# ---------------------------------------------------------------------------


def test_add_node_and_get_node():
    g = Graph()
    g.add_node("a", label="Alpha", value=1)
    assert g.get_node("a") == {"label": "Alpha", "value": 1}


def test_add_node_without_metadata():
    g = Graph()
    g.add_node("x")
    assert g.get_node("x") == {}


def test_add_node_merge_metadata():
    """Re-adding an existing node merges metadata; new values win."""
    g = Graph()
    g.add_node("a", x=1, y=2)
    g.add_node("a", y=99, z=3)
    assert g.get_node("a") == {"x": 1, "y": 99, "z": 3}


def test_get_node_missing_raises():
    g = Graph()
    with pytest.raises(KeyError):
        g.get_node("nonexistent")


# ---------------------------------------------------------------------------
# add_edge
# ---------------------------------------------------------------------------


def test_add_edge_creates_missing_nodes():
    g = Graph()
    g.add_edge("a", "b")
    # Both nodes should now exist
    assert g.get_node("a") == {}
    assert g.get_node("b") == {}


def test_add_edge_stores_metadata():
    g = Graph()
    g.add_edge("a", "b", weight=5, label="road")
    assert g.get_edge("a", "b") == {"weight": 5, "label": "road"}


def test_add_edge_directed_no_reverse():
    """a → b does NOT create b → a."""
    g = Graph()
    g.add_edge("a", "b")
    assert g.connected("a", "b") is True
    assert g.connected("b", "a") is False


# ---------------------------------------------------------------------------
# connected (direct edge only)
# ---------------------------------------------------------------------------


def test_connected_direct():
    g = Graph()
    g.add_edge("x", "y")
    assert g.connected("x", "y") is True


def test_connected_false_for_missing_edge():
    g = Graph()
    g.add_node("x")
    g.add_node("y")
    assert g.connected("x", "y") is False


def test_connected_false_for_reverse():
    g = Graph()
    g.add_edge("x", "y")
    assert g.connected("y", "x") is False


def test_connected_not_transitive():
    """connected() is NOT transitive — only checks direct edge."""
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    assert g.connected("a", "c") is False


# ---------------------------------------------------------------------------
# reachable (multi-hop BFS)
# ---------------------------------------------------------------------------


def test_reachable_direct():
    g = Graph()
    g.add_edge("a", "b")
    assert g.reachable("a", "b") is True


def test_reachable_multihop():
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    assert g.reachable("a", "d") is True


def test_reachable_false_no_path():
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("c", "d")
    assert g.reachable("a", "d") is False


def test_reachable_directed_only():
    """Reachability respects edge direction."""
    g = Graph()
    g.add_edge("a", "b")
    assert g.reachable("b", "a") is False


def test_reachable_self():
    """A node is reachable from itself (trivially)."""
    g = Graph()
    g.add_node("a")
    assert g.reachable("a", "a") is True


def test_reachable_missing_node():
    """If either node doesn't exist, return False — don't raise."""
    g = Graph()
    g.add_node("a")
    assert g.reachable("a", "z") is False
    assert g.reachable("z", "a") is False


def test_reachable_cycle_no_infinite_loop():
    """BFS must handle cycles without looping forever."""
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    # b IS reachable from a
    assert g.reachable("a", "b") is True
    # c is NOT reachable despite the cycle
    g.add_node("c")
    assert g.reachable("a", "c") is False


# ---------------------------------------------------------------------------
# neighbors
# ---------------------------------------------------------------------------


def test_neighbors_returns_direct_successors():
    g = Graph()
    g.add_edge("hub", "x")
    g.add_edge("hub", "y")
    g.add_edge("hub", "z")
    assert sorted(g.neighbors("hub")) == ["x", "y", "z"]


def test_neighbors_no_incoming_edges():
    """neighbors() only returns outgoing, not incoming."""
    g = Graph()
    g.add_edge("a", "hub")
    g.add_edge("b", "hub")
    assert g.neighbors("hub") == []


def test_neighbors_isolated_node():
    g = Graph()
    g.add_node("lone")
    assert g.neighbors("lone") == []


# ---------------------------------------------------------------------------
# get_edge
# ---------------------------------------------------------------------------


def test_get_edge_present():
    g = Graph()
    g.add_edge("a", "b", cost=3)
    assert g.get_edge("a", "b") == {"cost": 3}


def test_get_edge_missing_returns_none():
    g = Graph()
    g.add_edge("a", "b")
    assert g.get_edge("b", "a") is None


def test_get_edge_unknown_nodes_returns_none():
    g = Graph()
    assert g.get_edge("x", "y") is None


def test_get_edge_no_metadata():
    g = Graph()
    g.add_edge("a", "b")
    assert g.get_edge("a", "b") == {}


def test_get_edge_returns_copy():
    """Mutating the returned dict must not affect the stored edge."""
    g = Graph()
    g.add_edge("a", "b", weight=1)
    result = g.get_edge("a", "b")
    result["weight"] = 999
    assert g.get_edge("a", "b") == {"weight": 1}
