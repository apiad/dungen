"""Generic key-value state store with JSON-serializable value constraint."""

from __future__ import annotations

import copy
import json
from typing import Any


class State:
    """A generic key-value store whose values must be JSON-serializable."""

    def __init__(self, initial: dict | None = None) -> None:
        self._data: dict[str, Any] = {}
        if initial is not None:
            for key, value in initial.items():
                self.set(key, value)

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key*.

        Raises:
            TypeError: if *value* is not JSON-serializable.
        """
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"Value for key {key!r} is not JSON-serializable: {exc}"
            ) from exc
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if absent."""
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        """Return True if *key* exists in the store."""
        return key in self._data

    def keys(self) -> list[str]:
        """Return a list of all stored keys."""
        return list(self._data.keys())

    def snapshot(self) -> dict[str, Any]:
        """Return a deep copy of the internal store.

        Mutating the returned dict does not affect this State instance.
        """
        return copy.deepcopy(self._data)
