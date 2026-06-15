"""Directed graph primitive for the dungen simulation framework."""

from collections import deque


class Graph:
    """A directed graph with string node IDs and arbitrary metadata on nodes and edges."""

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, dict[str, dict]] = {}  # from_id -> {to_id -> metadata}

    def add_node(self, id: str, **metadata) -> None:
        """Add a node. If it already exists, metadata is merged (new values win)."""
        if id not in self._nodes:
            self._nodes[id] = {}
            self._edges[id] = {}
        self._nodes[id].update(metadata)

    def add_edge(self, from_id: str, to_id: str, **metadata) -> None:
        """Add a directed edge from_id → to_id. Implicitly creates missing nodes."""
        self.add_node(from_id)
        self.add_node(to_id)
        self._edges[from_id][to_id] = metadata

    def connected(self, a: str, b: str) -> bool:
        """Return True iff there is a direct edge a → b."""
        return b in self._edges.get(a, {})

    def reachable(self, a: str, b: str) -> bool:
        """Return True iff b is reachable from a by following directed edges (BFS)."""
        if a not in self._nodes or b not in self._nodes:
            return False
        visited: set[str] = set()
        queue: deque[str] = deque([a])
        while queue:
            current = queue.popleft()
            if current == b:
                return True
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self._edges.get(current, {}).keys())
        return False

    def neighbors(self, node_id: str) -> list[str]:
        """Return the list of nodes directly reachable from node_id (outgoing edges)."""
        return list(self._edges.get(node_id, {}).keys())

    def get_node(self, id: str) -> dict:
        """Return the metadata dict for a node. Raises KeyError if the node is missing."""
        if id not in self._nodes:
            raise KeyError(id)
        return dict(self._nodes[id])

    def get_edge(self, a: str, b: str) -> dict | None:
        """Return the metadata dict for edge a → b, or None if the edge does not exist."""
        edge = self._edges.get(a, {}).get(b)
        if edge is None:
            return None
        return dict(edge)
