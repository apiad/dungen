from typing import List, Dict, Optional
from pydantic import BaseModel, Field


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
        default_factory=list, description="IDs of other locations connected to this one"
    )


class Faction(BaseModel):
    """
    Represents a political or social group.
    """

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
        """Helper to find a location by ID."""
        for loc in self.locations:
            if loc.id == location_id:
                return loc
        return None
