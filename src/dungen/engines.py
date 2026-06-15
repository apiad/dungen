"""Engines — decision-making backends for characters in the simulation."""

from __future__ import annotations

import abc
import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from dungen.world import ActionDef, WorldSnapshot


# ---------------------------------------------------------------------------
# ActionCall — the output of any Engine.decide()
# ---------------------------------------------------------------------------


@dataclass
class ActionCall:
    """A resolved action name and its keyword arguments."""

    action: str
    args: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Engine — abstract base
# ---------------------------------------------------------------------------


class Engine(abc.ABC):
    """Abstract base for all character decision-making backends."""

    @abc.abstractmethod
    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
    ) -> ActionCall:
        """Return the ActionCall this engine chooses for the given character.

        Args:
            character: The entity (or user subclass) making the decision.
            perception: The dict produced by the perceive_fn for this character.
            world: A read-only WorldSnapshot at this point in time.
        """
        ...


# ---------------------------------------------------------------------------
# DeterministicEngine
# ---------------------------------------------------------------------------


class DeterministicEngine(Engine):
    """Engine driven by a plain synchronous function.

    The function receives ``(character, perception)`` and must return an
    :class:`ActionCall`.  It is called directly (no thread pool needed —
    deterministic functions are expected to be fast/pure).
    """

    def __init__(self, fn: Callable) -> None:
        self._fn = fn

    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
    ) -> ActionCall:
        return self._fn(character, perception)


# ---------------------------------------------------------------------------
# HumanEngine
# ---------------------------------------------------------------------------


def _default_cli_input(character: Any, perception: dict) -> ActionCall:
    """Default blocking CLI prompt for HumanEngine."""
    print(f"\n[{character.id}] Perception:\n{json.dumps(perception, indent=2)}")
    action = input("Action name: ").strip()
    raw_args = input("Args (JSON, or blank for {}): ").strip()
    args = json.loads(raw_args) if raw_args else {}
    return ActionCall(action=action, args=args)


class HumanEngine(Engine):
    """Engine that delegates to a human (or test stub) via a callable.

    If no ``input_fn`` is provided the engine blocks on a simple CLI prompt
    running in a thread so it does not block the event loop.

    ``input_fn`` may be synchronous or asynchronous:

    - **sync** → wrapped in :func:`asyncio.to_thread` automatically.
    - **async** → awaited directly.

    Signature: ``input_fn(character, perception) → ActionCall``
    """

    def __init__(self, input_fn: Callable | None = None) -> None:
        self._input_fn: Callable = input_fn or _default_cli_input

    async def decide(
        self,
        character: Any,
        perception: dict,
        world: "WorldSnapshot",
    ) -> ActionCall:
        fn = self._input_fn
        if inspect.iscoroutinefunction(fn):
            return await fn(character, perception)
        return await asyncio.to_thread(fn, character, perception)


# ---------------------------------------------------------------------------
# AgentEngine — LLM-driven via lingo
# ---------------------------------------------------------------------------

try:
    from lingo import LLM, Message
    from lingo.tools import DelegateTool, Tool

    _LINGO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LINGO_AVAILABLE = False


class _ActionTool:
    """Minimal lingo-compatible Tool built from an ActionDef.

    Rather than using DelegateTool (which wraps an actual callable), this class
    exposes the ActionDef's parameter schema for structured-output prompting
    while keeping the tool name and description.  The ``run`` method is never
    called inside the engine loop — commit tools return their ActionCall to the
    Simulation; read tools are executed via their stored ActionDef.fn.
    """

    def __init__(self, action_def: "ActionDef") -> None:
        self._def = action_def
        self._name = action_def.name
        self._description = action_def.description
        # Build parameter map from fn signature, skipping framework params.
        sig = inspect.signature(action_def.fn)
        self._params: dict[str, type] = {}
        for pname, param in sig.parameters.items():
            if pname in ("actor_id", "ctx"):
                continue
            ann = param.annotation
            if ann is inspect.Parameter.empty:
                ann = Any
            self._params[pname] = ann

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def parameters(self) -> dict[str, type]:
        return dict(self._params)

    def schema_description(self) -> str:
        """Human-readable parameter description for prompt injection."""
        if not self._params:
            return "(no parameters)"
        parts = [f"{k}: {v.__name__ if hasattr(v, '__name__') else str(v)}"
                 for k, v in self._params.items()]
        return ", ".join(parts)

    async def run(self, **kwargs: Any) -> Any:
        """Placeholder — never called inside AgentEngine."""
        raise NotImplementedError("_ActionTool.run should not be called directly")


def _build_action_menu(tools: list["_ActionTool"]) -> str:
    """Return a readable list of available actions for prompt injection."""
    lines = []
    for t in tools:
        lines.append(f"  - {t.name}({t.schema_description()}): {t.description}")
    return "\n".join(lines)


class AgentEngine(Engine):
    """LLM-driven engine using lingo for structured decision-making.

    Uses ``LLM.create`` (structured output) to select an action each turn,
    looping on read-only actions and returning the first commit action.

    Hook system
    -----------
    Register hooks with ``@engine.on(event_name)``.

    Supported events:

    ``before_turn``
        Fired before the LLM is consulted.
        Signature: ``async fn(character, messages, world) → list[Message] | None``

    ``after_read_action``
        Fired after each read-only action is executed inside the loop.
        Signature: ``async fn(character, messages, world, tool_result=...) → list[Message] | None``

    ``after_turn``
        Fired after the engine commits an action (or passes).
        Signature: ``async fn(character, messages, world) → list[Message] | None``

    ``on_checkpoint``
        For user-defined checkpointing.  Receives an extra ``name`` kwarg.
        Signature: ``async fn(character, messages, world, name=...) → list[Message] | None``

    If a hook returns a list, ``self._messages`` is replaced with that list.
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
        self._action_tools: list[_ActionTool] = []
        self._read_tools: list[_ActionTool] = []
        self._commit_tools: list[_ActionTool] = []

    # ------------------------------------------------------------------
    # Hook API
    # ------------------------------------------------------------------

    def on(self, event: str) -> Callable:
        """Decorator to register a hook for *event*.

        Example::

            @engine.on("after_turn")
            async def summarise(character, messages, world):
                ...  # optionally return a new list[Message]
        """
        if event not in self._hooks:
            raise ValueError(
                f"Unknown hook event {event!r}. "
                f"Valid events: {list(self._hooks)}"
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
        """Run all hooks for *event*.  If a hook returns a list, replace messages."""
        for hook in self._hooks.get(event, []):
            result = await hook(character, self._messages, world, **kwargs)
            if result is not None:
                self._messages = result

    # ------------------------------------------------------------------
    # Bind — called by Simulation before first turn
    # ------------------------------------------------------------------

    def bind(self, actions: dict[str, "ActionDef"]) -> None:
        """Attach action definitions to this engine.

        Builds ``_ActionTool`` wrappers and splits them into read vs commit
        lists.  Called by the Simulation before the first turn.
        """
        self._action_tools = []
        self._read_tools = []
        self._commit_tools = []
        for action_def in actions.values():
            t = _ActionTool(action_def)
            self._action_tools.append(t)
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
    ) -> ActionCall:
        """Run the agentic loop and return the chosen commit ActionCall.

        Strategy
        --------
        1. On the first call, initialise working memory with the system prompt.
        2. Fire ``before_turn`` hooks.
        3. Add perception as a user message.
        4. Enter the loop (capped at 20 iterations):
           a. Ask the LLM to pick an action via ``LLM.create`` (structured output).
           b. If the chosen action is a commit action, flush messages and return.
           c. If it is a read action, execute it, add the result, fire
              ``after_read_action`` hooks, and continue.
           d. If the LLM returns "pass" (or no valid action), return
              ``ActionCall("pass", {})``.
        5. Fire ``after_turn`` hooks before returning.
        """
        from pydantic import BaseModel, create_model
        from typing import Literal

        # Lazy initialise working memory.
        if not self._messages:
            self._messages = [Message.system(self._system_prompt)]

        await self._run_hooks("before_turn", character, world)

        # Build the turn message list (working memory + current perception).
        perception_text = json.dumps(perception, indent=2)
        turn_messages = list(self._messages) + [Message.user(perception_text)]

        all_tools = self._action_tools
        commit_names = {t.name for t in self._commit_tools}
        tool_map = {t.name: t for t in all_tools}

        # Build action-choice schema dynamically.
        # action_names includes "pass" as an escape hatch.
        action_names_list = [t.name for t in all_tools] + ["pass"]
        ActionName = Literal[tuple(action_names_list)]  # type: ignore[valid-type]

        class ActionChoice(BaseModel):
            """Choose an action and supply its arguments as a JSON object."""

            action: ActionName  # type: ignore[valid-type]
            args: dict = {}
            reasoning: str = ""

        # Build an actions menu to inject into the selection prompt.
        menu = _build_action_menu(all_tools)
        selection_prompt = (
            f"Available actions:\n{menu}\n\n"
            "Choose one action and supply its arguments. "
            "Use 'pass' to skip your turn with empty args."
        )

        for _ in range(20):  # safety cap
            # Ask the LLM to choose an action.
            prompt_messages = turn_messages + [Message.system(selection_prompt)]
            choice: ActionChoice = await self._llm.create(
                ActionChoice, prompt_messages
            )

            chosen = choice.action
            args = choice.args or {}

            if chosen == "pass" or chosen not in tool_map:
                # Agent chose to pass or returned an invalid action.
                self._messages = turn_messages
                await self._run_hooks("after_turn", character, world)
                return ActionCall("pass", {})

            if chosen in commit_names:
                # Commit action — return to Simulation for execution.
                self._messages = turn_messages
                await self._run_hooks("after_turn", character, world)
                return ActionCall(chosen, args)

            # Read action — execute inline and continue the loop.
            tool = tool_map[chosen]
            try:
                result = await tool._def.fn(
                    actor_id=character.id,
                    ctx=None,  # read actions should not need Context
                    **args,
                )
            except Exception as exc:
                result = f"Error: {exc}"

            result_text = json.dumps(result) if not isinstance(result, str) else result
            turn_messages.append(
                Message.assistant(f"Called {chosen}({args}) → {result_text}")
            )
            await self._run_hooks(
                "after_read_action", character, world, tool_result=result
            )

        # Safety cap reached — pass.
        self._messages = turn_messages
        await self._run_hooks("after_turn", character, world)
        return ActionCall("pass", {})
