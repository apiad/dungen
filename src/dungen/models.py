from typing import List, Dict, Optional
from pydantic import BaseModel, Field

# --- Worldbuilding Models (Architect) ---


class Location(BaseModel):
    """
    Represents a physical place in the world.
    In V0, this is a node in the graph with a static description.
    """

    id: str = Field(
        ..., description="Unique identifier for the location (e.g., 'iron_spire')"
    )
    name: str = Field(..., description="Display name of the location")
    description: str = Field(..., description="Sensory description of the location")
    connections: List[str] = Field(
        default_factory=list, description="IDs of connected locations"
    )


class Faction(BaseModel):
    id: str
    name: str
    ideology: str = Field(
        ..., description="The core belief system driving this faction"
    )
    description: Optional[str] = None


class World(BaseModel):
    """
    The static blueprint of the world (The Architect's Domain).
    This corresponds to the content of 'world.yaml'.
    """

    name: str = Field(..., description="The name of the world setting")
    description: str = Field(
        ..., description="High-level summary of the world's theme and history"
    )

    # We use lists for easy iteration, or Dicts for O(1) lookups.
    # Lists are often easier for LLMs to generate sequentially.
    locations: List[Location] = Field(default_factory=list)
    factions: List[Faction] = Field(default_factory=list)

    def get_location(self, location_id: str) -> Optional[Location]:
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        return None


# --- Roleplaying Models (Director) ---


class Character(BaseModel):
    """
    A playable avatar or major NPC.
    In V0/V1, acts as the persona filter for the LLM.
    """

    id: str = Field(..., description="Unique ID (e.g., 'detective_vance')")
    name: str = Field(..., description="Full name")
    role: str = Field(..., description="Archetype or Job (e.g., 'Disgraced Detective')")
    description: str = Field(..., description="Physical and personality summary")
    traits: List[str] = Field(
        default_factory=list,
        description="Key personality tags (e.g., 'Cynical', 'Sharp-shooter')",
    )
    # Global Attributes (0.0 - 1.0)
    resilience: float = Field(0.5, description="Physical/Mental toughness")
    sociability: float = Field(0.5, description="Ability to interact/persuade")


class Plot(BaseModel):
    """
    The 'Episode' definition.
    Defines the starting conditions and the narrative goal.
    Stored in ./plots/{id}.yaml
    """

    id: str = Field(..., description="Unique filename slug (e.g., 'spire_heist')")
    title: str = Field(..., description="The display title of the adventure")
    genre: str = Field(
        ..., description="Narrative style (e.g., 'Cyberpunk Noir', 'High Fantasy')"
    )
    premise: str = Field(..., description="The setup/hook for the story")
    goal: str = Field(..., description="The winning condition")

    starting_location_id: str = Field(..., description="Where the story begins")
    available_characters: List[Character] = Field(
        default_factory=list, description="Pre-generated cast options for this plot"
    )
