from typing import Any, List
from lingo.llm import LLM, Message
from pydantic import BaseModel, Field
from dungen.models import World, Plot, GameState
from dotenv import load_dotenv

load_dotenv()

# System prompt for the Architect persona
ARCHITECT_SYSTEM_PROMPT = """
You are the Architect, a master world-builder for a narrative RPG engine.
Your goal is to design consistent, thematic, and interesting settings based on user prompts.
When defining factions, ensure they have conflicting ideologies to drive drama.
When defining locations, ensure they are distinct and support the intended atmosphere.
"""


async def generate_world(prompt: str) -> World:
    """
    Creates a brand new World blueprint from a high-level text description.
    """
    llm = LLM()

    messages = [
        Message.system(ARCHITECT_SYSTEM_PROMPT),
        Message.user(f"Design a world based on this concept: {prompt}"),
    ]

    # Use Lingo's structured generation to guarantee a valid World object
    world = await llm.create(World, messages)
    return world


async def update_world(current_world: World, command: str) -> World:
    """
    Applies surgical or sweeping changes to an existing World based on a command.
    """
    llm = LLM()

    messages = [
        Message.system(ARCHITECT_SYSTEM_PROMPT),
        Message.user("Here is the current world definition:"),
        Message.user(
            current_world
        ),  # Lingo automatically serializes the Pydantic model
        Message.user(f"Apply this change/update to the world: {command}"),
    ]

    # The LLM returns a new, modified World object
    updated_world = await llm.create(World, messages)
    return updated_world


# --- Scriptwriter Persona (Plot/Episode Design) ---

SCRIPTWRITER_SYSTEM_PROMPT = """
You are the Scriptwriter, a lead narrative designer for a dynamic roleplaying engine.
Your goal is to design structured narrative episodes (Plots) using a directed graph of Narrative Nodes.

GUIDELINES:
1. **The Graph:** Define a `narrative_graph` of connected Nodes.
2. **Nodes:** Each `NarrativeNode` represents a state of the story (e.g., 'intro', 'combat_encounter', 'investigation').
3. **Atmosphere:** For each node, define a distinct `atmosphere` (e.g., "Tense and quiet" vs "Chaotic and loud").
4. **Transitions:** Define logical `transitions` between nodes based on player actions (e.g., "If player attacks -> go to combat_node").
5. **Connectivity:** Ensure the `starting_node_id` exists and that the graph has no unavoidable dead ends unless they are terminal states.
6. **Characters:** Create a cast that fits the Genre and World.

Ensure IDs are snake_case.
"""


async def generate_plot(prompt: str, world: World) -> Plot:
    """Creates a new Plot (Episode) based on a premise, grounded in the provided World."""
    llm = LLM()
    messages = [
        Message.system(SCRIPTWRITER_SYSTEM_PROMPT),
        Message.user("Context: This plot takes place in the following world:"),
        Message.user(world),
        Message.user(f"Write a plot/episode based on this idea: {prompt}"),
    ]
    return await llm.create(Plot, messages)


async def update_plot(current_plot: Plot, command: str, world: World) -> Plot:
    """Refines or modifies an existing Plot with context of the world."""
    llm = LLM()
    messages = [
        Message.system(SCRIPTWRITER_SYSTEM_PROMPT),
        Message.user("Context: This plot takes place in the following world:"),
        Message.user(world),
        Message.user("Here is the current plot draft:"),
        Message.user(current_plot),
        Message.user(f"Apply this change/update to the plot: {command}"),
    ]
    return await llm.create(Plot, messages)


# --- Director Persona (Simultaneous Scene Resolution) ---

# --- Director Persona (Simultaneous Scene Resolution) ---


class StateUpdate(BaseModel):
    """A specific change to an actor or the world."""

    target_id: str = Field(..., description="ID of the actor or 'WORLD' or 'NARRATIVE'")
    field: str = Field(
        ...,
        description="Field to update (e.g., 'health', 'location', 'status', 'inventory')",
    )
    value: Any = Field(..., description="The new value")
    reason: str = Field(..., description="Why this change happened")


class SceneResolution(BaseModel):
    """The structured output of a turn."""

    narrative_prose: str = Field(
        ..., description="The story text describing what happened."
    )
    updates: List[StateUpdate] = Field(
        default_factory=list, description="List of mechanical changes."
    )
    next_node_id: str = Field(
        ..., description="The ID of the next narrative node (can be same as current)."
    )


DIRECTOR_SYSTEM_PROMPT = """
You are the Director, a realtime roleplaying engine.
Your goal is to resolve the current scene by simulating the interaction between the Player and all Local Actors.

INPUTS:
1. **World & Location:** The setting description.
2. **Narrative Node:** The current "Vibe", "Atmosphere", and "Director Instructions" (Priority).
3. **Actors:** The current state of the Player and all NPCs in the room.
4. **Action:** What the player wants to do.

LOGIC:
1. **Simultaneity:** Resolve everyone's actions at once. If the player attacks, does the guard defend? If the player speaks, does the NPC interrupt?
2. **Atmosphere:** Ensure the `narrative_prose` matches the `atmosphere` of the current Node.
3. **Transitions:** Check the `transitions` in the current Node. If the player's action matches a condition, update `next_node_id`.
4. **Consequences:** If an action succeeds/fails, generate `StateUpdates` (damage, item transfer, status effects).

OUTPUT:
Return a `SceneResolution` object with the story prose and state changes.
"""


async def resolve_scene(
    world: World, plot: Plot, game_state: GameState, player_action: str
) -> SceneResolution:
    """
    Simulates a single turn.
    """
    llm = LLM()

    # 1. Gather Context using the new GameState helpers
    current_node = plot.get_node(game_state.current_node_id)
    current_location = world.get_location(game_state.current_location_id)
    local_actors = (
        game_state.get_local_actors()
    )  # Now works because GameState knows the location

    # 2. Construct the Prompt
    messages = [
        Message.system(DIRECTOR_SYSTEM_PROMPT),
        # Context Injection
        Message.user(f"--- CONTEXT: {current_node.title} ---"),
        Message.user(f"Atmosphere: {current_node.atmosphere}"),
        Message.user(f"Director Instructions: {current_node.description}"),
        Message.user(
            f"Location: {current_location.name} - {current_location.description}"
        ),
        # Graph Logic
        Message.user(f"Current node id: {current_node.id}"),
        Message.user("Potential Transitions:"),
        Message.user(current_node.transitions),
        # Actor States
        Message.user("--- ACTORS IN SCENE ---"),
        Message.user(local_actors),
        # The Trigger
        Message.user("--- ACTION ---"),
        Message.user(f"Player Action: {player_action}"),
        Message.user("Resolve the scene."),
    ]

    # 3. Invoke LLM
    result = await llm.create(SceneResolution, messages)
    return result
