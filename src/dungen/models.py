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

    def get_location(self, location_id: str) -> Location:
        for loc in self.locations:
            if loc.id == location_id:
                return loc

        raise KeyError(location_id)


# --- Roleplaying Models (Director) ---


class Character(BaseModel):
    """
    A playable avatar or major NPC.
    """

    id: str = Field(..., description="Unique ID (e.g., 'detective_vance')")
    name: str = Field(..., description="Full name")
    role: str = Field(..., description="Archetype or Job (e.g., 'Disgraced Detective')")
    description: str = Field(..., description="Physical and personality summary")
    traits: List[str] = Field(default_factory=list, description="Key personality tags")
    resilience: float = Field(0.5, description="Physical/Mental toughness (0.0-1.0)")
    sociability: float = Field(
        0.5, description="Ability to interact/persuade (0.0-1.0)"
    )


# --- Narrative Graph Models (The Flowchart) ---


class Transition(BaseModel):
    """
    A conditional link between two narrative nodes.
    """

    target_node: str = Field(..., description="The ID of the NarrativeNode to move to.")
    condition: str = Field(
        ...,
        description="The narrative trigger (e.g., 'Player finds the Key', 'Player kills the Guard').",
    )


class NarrativeNode(BaseModel):
    """
    A single state in the narrative flowchart.
    Controls the 'Vibe' and the Director's priorities.
    """

    id: str = Field(
        ..., description="Unique ID (e.g., 'intro_investigation', 'chase_sequence')"
    )
    title: str = Field(..., description="Display title for the beat")
    description: str = Field(
        ...,
        description="Director instructions: What is happening? What should the engine prioritize?",
    )
    atmosphere: str = Field(
        ..., description="Narrator instructions: Sensory details, tone, and pacing."
    )
    transitions: List[Transition] = Field(
        default_factory=list,
        description="Possible branches from this state. If empty, the state is static.",
    )
    is_terminal: bool = Field(
        False,
        description="If True, the episode ends when this node is reached (Win/Loss).",
    )


class Plot(BaseModel):
    """
    The 'Episode' definition containing the narrative graph.
    """

    id: str = Field(..., description="Unique filename slug")
    title: str = Field(..., description="Display title")
    genre: str = Field(..., description="Narrative style")
    premise: str = Field(..., description="High-level summary")
    goal: str = Field(..., description="The ultimate winning condition")

    # World Hook
    starting_location_id: str = Field(
        ..., description="Physical entry point in the World"
    )

    # Narrative Structure
    narrative_graph: List[NarrativeNode] = Field(
        default_factory=list, description="The flowchart of story beats/states."
    )
    starting_node_id: str = Field(..., description="The ID of the first NarrativeNode")

    available_characters: List[Character] = Field(
        default_factory=list, description="Pre-generated cast options"
    )

    def get_node(self, node_id: str) -> NarrativeNode:
        for node in self.narrative_graph:
            if node.id == node_id:
                return node

        raise KeyError(node_id)


# --- Runtime / Session Models (The Simulation) ---


class ActorState(BaseModel):
    """
    The dynamic state of a character in a specific session.
    Changes every turn (health, location, memory).
    """
    id: str = Field(..., description="Links to the Character blueprint ID")
    location_id: str = Field(..., description="Current location in the world")
    current_health: float = Field(1.0, description="Health percentage (0.0 - 1.0)")
    status_effects: List[str] = Field(default_factory=list, description="Tags like 'alert', 'unconscious', 'hiding'")
    inventory: List[str] = Field(default_factory=list, description="List of item IDs")
    memory: List[str] = Field(
        default_factory=list,
        description="Short-term observations (e.g., 'Saw player draw weapon')"
    )
    relationships: Dict[str, float] = Field(
        default_factory=dict,
        description="Dynamic reputation with other actors (-1.0 to 1.0)"
    )

class GameState(BaseModel):
    """
    The complete snapshot of a running game session.
    Stored in state.yaml.
    """
    session_id: str
    turn_count: int = 0

    # Narrative Context
    current_plot_id: str
    current_node_id: str

    # The Protagonist (The anchor for the simulation)
    player_id: str = Field(..., description="The ID of the actor controlled by the user")

    # Simulation Data
    # Registry of all active/tracked actors. Key is actor ID.
    actors: Dict[str, ActorState] = Field(default_factory=dict)

    world_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Global switches (e.g., 'alarm_triggered': True)"
    )

    @property
    def player(self) -> ActorState:
        """Helper to get the player's actor object."""
        return self.actors[self.player_id]

    @property
    def current_location_id(self) -> str:
        """The 'Camera' location (always follows the player)."""
        return self.player.location_id

    def get_actor(self, actor_id: str) -> Optional[ActorState]:
        return self.actors.get(actor_id)

    def get_local_actors(self) -> List[ActorState]:
        """Returns all actors (Player + NPCs) in the current scene."""
        loc = self.current_location_id
        return [a for a in self.actors.values() if a.location_id == loc]

class Event(BaseModel):
    turn: int
    location_id: str
    node_id: str
    actor_ids: List[str]
    player_action: str
    narrative_outcome: str
    mechanical_updates: List[str]

class Ledger(BaseModel):
    events: List[Event] = Field(default_factory=list)