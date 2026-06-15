import pytest

from dungen.inventory import Inventory


# ---------------------------------------------------------------------------
# add / contains / list
# ---------------------------------------------------------------------------

def test_add_and_contains():
    inv = Inventory()
    assert not inv.contains("sword")
    inv.add("sword")
    assert inv.contains("sword")


def test_list_empty():
    inv = Inventory()
    assert inv.list() == []


def test_list_preserves_insertion_order():
    inv = Inventory()
    inv.add("torch")
    inv.add("sword")
    inv.add("torch")
    assert inv.list() == ["torch", "sword", "torch"]


def test_list_returns_snapshot():
    inv = Inventory()
    inv.add("torch")
    snapshot = inv.list()
    inv.add("sword")
    # snapshot must not reflect the later addition
    assert snapshot == ["torch"]


# ---------------------------------------------------------------------------
# remove
# ---------------------------------------------------------------------------

def test_remove_present_returns_true():
    inv = Inventory()
    inv.add("key")
    result = inv.remove("key")
    assert result is True
    assert not inv.contains("key")


def test_remove_absent_returns_false():
    inv = Inventory()
    result = inv.remove("key")
    assert result is False


def test_remove_leaves_inventory_unchanged_when_absent():
    inv = Inventory()
    inv.add("torch")
    inv.remove("key")
    assert inv.list() == ["torch"]


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------

def test_add_twice_creates_two_entries():
    inv = Inventory()
    inv.add("torch")
    inv.add("torch")
    assert inv.list().count("torch") == 2


def test_remove_once_leaves_duplicate():
    inv = Inventory()
    inv.add("torch")
    inv.add("torch")
    inv.remove("torch")
    assert inv.contains("torch")
    assert inv.list().count("torch") == 1


def test_remove_removes_first_occurrence():
    inv = Inventory()
    inv.add("a")
    inv.add("torch")
    inv.add("torch")
    inv.add("b")
    inv.remove("torch")
    assert inv.list() == ["a", "torch", "b"]


# ---------------------------------------------------------------------------
# transfer
# ---------------------------------------------------------------------------

def test_transfer_happy_path():
    src = Inventory()
    dst = Inventory()
    src.add("gem")
    result = src.transfer("gem", dst)
    assert result is True
    assert not src.contains("gem")
    assert dst.contains("gem")


def test_transfer_item_not_in_source_returns_false():
    src = Inventory()
    dst = Inventory()
    result = src.transfer("gem", dst)
    assert result is False


def test_transfer_does_not_mutate_when_absent():
    src = Inventory()
    dst = Inventory()
    dst.add("existing")
    src.transfer("ghost", dst)
    assert dst.list() == ["existing"]
    assert src.list() == []


def test_transfer_moves_only_one_copy():
    src = Inventory()
    dst = Inventory()
    src.add("coin")
    src.add("coin")
    src.transfer("coin", dst)
    assert src.list().count("coin") == 1
    assert dst.list().count("coin") == 1
