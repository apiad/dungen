from __future__ import annotations


class Inventory:
    """An ordered multiset of item IDs.

    Items are stored in insertion order; duplicates are allowed.
    All operations work on a single occurrence at a time.
    """

    def __init__(self) -> None:
        self._items: list[str] = []

    def add(self, item_id: str) -> None:
        """Append one copy of *item_id* to the inventory."""
        self._items.append(item_id)

    def remove(self, item_id: str) -> bool:
        """Remove one occurrence of *item_id*.

        Returns True if an item was removed, False if it was not present.
        """
        try:
            self._items.remove(item_id)
            return True
        except ValueError:
            return False

    def contains(self, item_id: str) -> bool:
        """Return True if at least one copy of *item_id* is present."""
        return item_id in self._items

    def list(self) -> list[str]:
        """Return a snapshot of all items in insertion order (duplicates included)."""
        return list(self._items)

    def transfer(self, item_id: str, target: "Inventory") -> bool:
        """Move one copy of *item_id* from this inventory to *target*.

        Returns True on success.  Returns False (without mutating either
        inventory) if *item_id* is not present in self.
        """
        if not self.remove(item_id):
            return False
        target.add(item_id)
        return True
