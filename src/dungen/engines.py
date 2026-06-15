"""Engines — decision-making backends for characters in the simulation."""

from __future__ import annotations

import abc
import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from dungen.world import ActionDef, World, WorldSnapshot


# ---------------------------------------------------------------------------
# ActionCall — the output of any Engine.decide()
# ---------------------------------------------------------------------------


@dataclass
class ActionCall:
    action: str
    args: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine — abstract base
# ---------------------------------------------------------------------------


class Engine(abc.ABC):
    @abc.abstractmethod
    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
        turn: int,
    ) -> ActionCall:
        ...


# ---------------------------------------------------------------------------
# DeterministicEngine
# ---------------------------------------------------------------------------


class DeterministicEngine(Engine):
    def __init__(self, fn: Callable) -> None:
        # fn(character, perception) → ActionCall  (sync)
        self._fn = fn

    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
        turn: int,
    ) -> ActionCall:
        return self._fn(character, perception)


# ---------------------------------------------------------------------------
# HumanEngine
# ---------------------------------------------------------------------------


def _default_cli_input(character: Any, perception: dict) -> ActionCall:
    print(f"\n[{character.id}] Perception:\n{json.dumps(perception, indent=2)}")
    action = input("Action name: ").strip()
    raw_args = input("Args (JSON, or blank for {}): ").strip()
    args = json.loads(raw_args) if raw_args else {}
    return ActionCall(action=action, args=args)


class HumanEngine(Engine):
    def __init__(self, input_fn: Callable | None = None) -> None:
        self._input_fn: Callable = input_fn or _default_cli_input

    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
        turn: int,
    ) -> ActionCall:
        fn = self._input_fn
        if inspect.iscoroutinefunction(fn):
            return await fn(character, perception)
        return await asyncio.to_thread(fn, character, perception)


# ---------------------------------------------------------------------------
# AgentEngine — LLM-driven via Lingo native tool-calling
# ---------------------------------------------------------------------------

try:
    from lingo import LLM, Message
    _LINGO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LINGO_AVAILABLE = False


class _ActionTool:
    """Lingo-compatible Tool built from an ActionDef.

    Exposes name, description, and parameters() for schema serialization.
    run() is only used for read tools (calls the action fn with actor_id + ctx).
    Commit tools: Simulation executes them — run() is never called.
    """

    def __init__(self, action_def: "ActionDef") -> None:
        self._def = action_def
        self._actor_id: str | None = None
        self._ctx: Any = None

        sig = inspect.signature(action_def.fn)
        self._params: dict[str, type] = {}
        for pname, param in sig.parameters.items():
            if pname in ("actor_id", "ctx"):
                continue
            ann = param.annotation
            if ann is inspect.Parameter.empty:
                ann = Any
            self._params[pname] = ann

    def bind(self, actor_id: str, ctx: Any) -> "_ActionTool":
        """Return self with actor_id and ctx bound for run()."""
        self._actor_id = actor_id
        self._ctx = ctx
        return self

    @property
    def name(self) -> str:
        return self._def.name

    @property
    def description(self) -> str:
        return self._def.description

    def parameters(self) -> dict[str, type]:
        return dict(self._params)

    async def run(self, **kwargs: Any) -> Any:
        return await self._def.fn(
            actor_id=self._actor_id,
            ctx=self._ctx,
            **kwargs,
        )


class AgentEngine(Engine):
    """LLM-driven engine using Lingo's native tool-calling loop.

    Read tools (commits=False) are executed inline inside the loop; the LLM
    sees their results and continues deciding.  Commit tools (commits=True) are
    NOT executed here — their name+args are returned as an ActionCall and the
    Simulation resolves them via Context.

    Hook system
    -----------
    Register hooks with @engine.on(event_name).

    Supported events:
    - before_turn: async fn(character, messages, world) → list[Message] | None
    - after_read_action: async fn(character, messages, world, tool_result=...) → list[Message] | None
    - after_turn: async fn(character, messages, world) → list[Message] | None
    - on_checkpoint: async fn(character, messages, world, name=...) → list[Message] | None

    If a hook returns a list it replaces the engine's working memory.
    """

    def __init__(self, llm: "LLM", system_prompt: str) -> None:
        if not _LINGO_AVAILABLE:
            raise ImportError("lingo-ai must be installed to use AgentEngine")
        self._llm = llm
        self._system_prompt = system_prompt
        self._hooks: dict[str, list[Callable]] = {
            "before_turn": [],
            "after_read_action": [],
            "after_turn": [],
            "on_checkpoint": [],
        }
        self._messages: list["Message"] = []
        self._read_tools: list[_ActionTool] = []
        self._commit_tools: list[_ActionTool] = []
        self._world: "World | None" = None

    # ------------------------------------------------------------------
    # Hook API
    # ------------------------------------------------------------------

    def on(self, event: str) -> Callable:
        """Decorator to register a hook for *event*."""
        if event not in self._hooks:
            raise ValueError(
                f"Unknown hook event {event!r}. Valid: {list(self._hooks)}"
            )

        def decorator(fn: Callable) -> Callable:
            self._hooks[event].append(fn)
            return fn

        return decorator

    async def _run_hooks(
        self,
        event: str,
        character: Any,
        world: "WorldSnapshot",
        **kwargs: Any,
    ) -> None:
        for hook in self._hooks.get(event, []):
            result = await hook(character, self._messages, world, **kwargs)
            if result is not None:
                self._messages = result

    # ------------------------------------------------------------------
    # Bind — called by Simulation before first turn
    # ------------------------------------------------------------------

    def bind(self, actions: dict[str, "ActionDef"], world: "World") -> None:
        """Attach action definitions and live World reference.

        Called by Simulation before the first turn. The World reference is
        used to construct a Context for read-tool execution.
        """
        self._world = world
        self._read_tools = []
        self._commit_tools = []
        for action_def in actions.values():
            t = _ActionTool(action_def)
            if action_def.commits:
                self._commit_tools.append(t)
            else:
                self._read_tools.append(t)

    # ------------------------------------------------------------------
    # decide()
    # ------------------------------------------------------------------

    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
        turn: int,
    ) -> ActionCall:
        from dungen.context import Context

        # Lazy-init working memory.
        if not self._messages:
            self._messages = [Message.system(self._system_prompt)]

        await self._run_hooks("before_turn", character, world)

        perception_text = json.dumps(perception, indent=2)
        turn_messages = list(self._messages) + [Message.user(perception_text)]

        # Build a Context for read-tool execution this turn.
        ctx = Context(self._world, turn) if self._world else None

        # Bind actor + ctx into read tools (commit tools are never run() here).
        read_tools = [t.bind(character.id, ctx) for t in self._read_tools]
        commit_names = {t.name for t in self._commit_tools}
        all_tools = read_tools + self._commit_tools

        for _ in range(20):  # safety cap
            msg = await self._llm.chat(turn_messages, tools=all_tools)
            turn_messages.append(msg)

            if not msg.tool_calls:
                # LLM chose not to call a tool — pass this turn.
                self._messages = turn_messages
                await self._run_hooks("after_turn", character, world)
                return ActionCall("pass", {})

            # Check for a commit tool call — return immediately.
            for call in msg.tool_calls:
                if call.name in commit_names:
                    self._messages = turn_messages
                    await self._run_hooks("after_turn", character, world)
                    return ActionCall(call.name, call.arguments)

            # Only read tool calls this round — execute and feed results back.
            tool_by_name = {t.name: t for t in read_tools}
            for call in msg.tool_calls:
                tool = tool_by_name.get(call.name)
                if tool is None:
                    result = f"Unknown action: {call.name}"
                else:
                    try:
                        result = await tool.run(**call.arguments)
                    except Exception as exc:
                        result = f"Error: {exc}"
                result_str = json.dumps(result) if not isinstance(result, str) else result
                turn_messages.append(Message.tool(result_str, tool_call_id=call.id))
                await self._run_hooks("after_read_action", character, world, tool_result=result)

        # Safety cap — pass.
        self._messages = turn_messages
        await self._run_hooks("after_turn", character, world)
        return ActionCall("pass", {})
