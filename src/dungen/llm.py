from lingo.llm import LLM, Message
from dungen.models import World, Plot
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
Your goal is to design structured narrative episodes (Plots) that provide a solid foundation for gameplay.
A Plot must have a clear Genre, a gripping Premise, and a specific Goal for the player.
You must also design a cast of Available Characters that fit the setting and genre.
Ensure the 'id' fields are snake_case and unique-ish.
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
