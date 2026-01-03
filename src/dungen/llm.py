from lingo.llm import LLM, Message
from dungen.models import World
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
