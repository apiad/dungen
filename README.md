# dungen

**A text-based world builder, roleplay engine, and story generator.**

`dungen` is a modern, AI-native framework for creating, playing, and narrating persistent text-based worlds. It moves beyond static state machines to a dynamic simulation powered by Large Language Models (LLMs), allowing for emergent gameplay and collaborative storytelling.

## The Vision: The Three Pillars

`dungen` is built on the strict separation of concerns between three distinct narrative modes:

1. **The Architect (Worldbuilding Mode):** Used to design the static "blueprint" of the world. In this mode, the user makes surgical or sweeping changes to the geography, factions, and ideologies of the world.
2. **The Director (Roleplaying Mode):** The "physics engine" of the narrative. It resolves player and NPC actions based on the current world state, attributes, and moral stances, logging every atomic event into a chronicle ledger.
3. **The Skald (Storytelling Mode):** The prose layer. It takes the raw data from the simulation and renders it into immersive, sensory-driven prose filtered through specific points of view (POV) and genres.

## Roadmap: Levels of Complexity

`dungen` is being developed through increasing levels of simulation complexity.

* **V0: The Core Loop (Current):** Minimal "Reality Bubble" implementation. LLM resolves any text action within a single-location context.
* **V1: Identity:** Actors receive attributes (0-1 scales). Personalities and traits begin to influence outcomes.
* **V2: Spatiality & Factions:** Locations become a connected graph. Factions and Ideologies are introduced to rule specific regions.
* **V3: The Persistent Mind:** Implementation of the BDI (Belief-Desire-Intention) model. Actors act based on subjective beliefs that can be true or false.
* **V4: The Causal World:** A background "Tick" system allows the world to change autonomously while the player is away.

## Getting Started

### Installation

`dungen` uses [uv](https://github.com/astral-sh/uv) for modern, high-performance dependency management.

```bash
# Clone the repository
git clone https://github.com/apiad/dungen
cd dungen

# Install dependencies and create a virtual environment
uv sync

```

### Usage

The framework provides a unified CLI for interacting with the three modes:

* **Build the World:**
```bash
uv run dungen build "Add a hidden rebel outpost in the industrial district"

```


* **Play the Game:**
```bash
uv run dungen play

```


* **Narrate the Story:**
```bash
uv run dungen narrate --pov player

```



## Persistence Layer

The world is stored in three hierarchical YAML files to ensure transparency and easy editing:

* `world.yaml`: Static definitions of factions, geography, and ideologies.
* `state.yaml`: The dynamic "live" state of actors, inventories, and world flags.
* `ledger.yaml`: An immutable, chronological history of every event for the Skald to process.

## Origins

This project is a modern reboot of the original `dungen` engine, a text-based dungeon generator and engine written in Python. While the original relied on fixed YAML state machines, the new framework leverages LLMs for a "Universal Resolver" approach.

## License

This project is licensed under the MIT License.
Copyright (c) 2018-2026 Alejandro Piad.
