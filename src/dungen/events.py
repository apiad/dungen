"""SimEvent dataclasses — events yielded by Simulation.run()."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union


@dataclass
class TurnStarted:
    turn: int


@dataclass
class AgentThinking:
    turn: int
    actor_id: str


@dataclass
class ReadActionCalled:
    turn: int
    actor_id: str
    action: str
    args: dict
    result: Any


@dataclass
class ActionCommitted:
    turn: int
    actor_id: str
    action: str
    args: dict
    result: Any


@dataclass
class TurnResolved:
    turn: int
    committed: list[ActionCommitted] = field(default_factory=list)


@dataclass
class HookFired:
    turn: int
    actor_id: str
    hook_name: str


@dataclass
class SimulationEnded:
    reason: str  # "max_turns" | "until_condition" | "no_agents"


SimEvent = Union[
    TurnStarted,
    AgentThinking,
    ReadActionCalled,
    ActionCommitted,
    TurnResolved,
    HookFired,
    SimulationEnded,
]
