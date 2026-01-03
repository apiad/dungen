import typer
import asyncio
import os
import yaml
import time
from typing import List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.columns import Columns
from rich.table import Table
from rich.text import Text
from rich import box

# Import from our modules
from dungen.models import World, Plot, GameState, ActorState, Ledger, Event, Character
from dungen.llm import (
    generate_world,
    update_world,
    generate_plot,
    update_plot,
    resolve_scene,
    SceneResolution,
)

# ... (Existing App and Constants) ...

app = typer.Typer(
    no_args_is_help=True,
    name="dungen",
    help="A text-based world builder, roleplay engine, and story generator.",
)
console = Console()

# --- CONSTANTS ---
WORLD_FILE = "world.yaml"
PLOTS_DIR = "plots"
SAVES_DIR = "saves"


# --- PERSISTENCE HELPERS ---


def save_world(world: World):
    """Persist the World object to YAML."""
    with open(WORLD_FILE, "w") as f:
        yaml.dump(world.model_dump(), f, sort_keys=False)


def load_world() -> World | None:
    """Load the World object from YAML if it exists."""
    if not os.path.exists(WORLD_FILE):
        return None
    with open(WORLD_FILE, "r") as f:
        data = yaml.safe_load(f)
    return World(**data)


def save_plot(plot: Plot, filename: str):
    """Persist a Plot object to the plots directory."""
    os.makedirs(PLOTS_DIR, exist_ok=True)
    filepath = os.path.join(PLOTS_DIR, filename)
    with open(filepath, "w") as f:
        yaml.dump(plot.model_dump(), f, sort_keys=False)


def load_plot(filename: str) -> Plot | None:
    """Load a Plot object from the plots directory."""
    filepath = os.path.join(PLOTS_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r") as f:
        data = yaml.safe_load(f)
    return Plot(**data)


# --- UI COMPONENTS ---


def get_main_view(history: list, persona: str) -> Panel:
    """Generates the main conversation view."""
    if not history:
        welcome_md = Markdown(
            f"""
# Welcome, {persona}.

The studio is open. You can:
* **Describe** changes you want to make.
* **Refine** details.
* **Ask** for suggestions.

*Type 'exit' to save and quit.*
            """
        )
        return Panel(
            welcome_md, title="Activity Log", border_style="white", box=box.ROUNDED
        )

    # Render the last few history items
    table = Table(box=None, show_header=False, padding=(0, 0, 1, 0))
    table.add_column("Content")

    for role, text in history[-5:]:  # Show last 5 interactions
        if role == "user":
            table.add_row(f"[bold blue]{persona} >[/bold blue] {text}")
        else:
            table.add_row(f"[dim]{text}[/dim]")

    return Panel(table, title="Activity Log", border_style="white", box=box.ROUNDED)


def get_world_sidebar(world: World) -> Panel:
    """Generates the side panel showing the current world state."""
    info_text = Text()
    info_text.append(f"{world.name}\n", style="bold cyan underline")
    desc = (
        world.description[:150] + "..."
        if len(world.description) > 150
        else world.description
    )
    info_text.append(f"{desc}\n\n", style="italic dim")

    info_text.append("Locations:\n", style="bold green")
    if world.locations:
        for loc in world.locations:
            info_text.append(f"• {loc.name}\n", style="green")
    else:
        info_text.append("• None\n", style="dim")
    info_text.append("\n")

    info_text.append("Factions:\n", style="bold yellow")
    if world.factions:
        for fac in world.factions:
            info_text.append(f"• {fac.name}\n", style="yellow")
    else:
        info_text.append("• None\n", style="dim")

    return Panel(
        info_text,
        title="[bold]World State[/bold]",
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 2),
    )


def get_plot_sidebar(plot: Plot) -> Panel:
    """Generates the side panel showing the current narrative plot."""
    info_text = Text()
    info_text.append(f"{plot.title}\n", style="bold magenta underline")
    info_text.append(f"[{plot.genre}]\n\n", style="italic white")

    info_text.append("Goal:\n", style="bold red")
    info_text.append(f"{plot.goal}\n\n", style="white")

    info_text.append("Cast:\n", style="bold cyan")
    if plot.available_characters:
        for char in plot.available_characters:
            info_text.append(f"• {char.name}", style="cyan")
            info_text.append(f" ({char.role})\n", style="dim cyan")
    else:
        info_text.append("• None\n", style="dim")

    info_text.append("\nStarting Point:\n", style="bold green")
    info_text.append(f"{plot.starting_location_id}", style="dim green")

    return Panel(
        info_text,
        title="[bold]Script Draft[/bold]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(1, 2),
    )


# --- LOOPS ---


async def build_loop():
    """The Architect Mode Loop (Worldbuilding)."""
    world = load_world()
    history = []

    if not world:
        console.clear()
        console.print(
            Panel(
                "[bold green]dungen: Architect Mode[/bold green]",
                subtitle="Initialization",
            )
        )
        console.print(
            "[yellow]No 'world.yaml' found. Let's create a new world.[/yellow]"
        )
        prompt = console.input(
            "[bold green]Describe your world concept > [/bold green]"
        )

        with console.status(
            "[bold green]The Architect is designing the blueprint...[/bold green]",
            spinner="earth",
        ):
            world = await generate_world(prompt)
        save_world(world)
        history.append(("user", f"Create world: {prompt}"))
        history.append(("system", "World initialized."))

    while True:
        console.clear()
        sidebar = get_world_sidebar(world)
        main_view = get_main_view(history, "Architect")
        console.print(Columns([main_view, sidebar], expand=True, equal=False))

        command = console.input("\n[bold blue]Command > [/bold blue]")
        if command.lower() in ["exit", "quit", "q"]:
            break

        with console.status("[bold blue]Refining world...[/bold blue]", spinner="dots"):
            try:
                world = await update_world(world, command)
                save_world(world)
                history.append(("user", command))
                changes = f"Locs: {len(world.locations)} | Facs: {len(world.factions)}"
                history.append(("system", f"Update applied. ({changes})"))
            except Exception as e:
                history.append(("user", command))
                history.append(("system", f"[bold red]Error:[/bold red] {str(e)}"))


async def plot_loop(name: str):
    """The Scriptwriter Mode Loop (Plot Design)."""
    # 1. Load the world context first
    world = load_world()
    if not world:
        console.print("[bold red]Error:[/bold red] No 'world.yaml' found.")
        console.print("You must build a world before writing a script.")
        console.print("Run [green]dungen build[/green] first.")
        return

    filename = f"{name}.yaml"
    plot = load_plot(filename)
    history = []

    if not plot:
        console.clear()
        console.print(
            Panel(
                "[bold magenta]dungen: Scriptwriter Mode[/bold magenta]",
                subtitle="Pre-Production",
            )
        )
        console.print(f"[dim]World Context: {world.name}[/dim]")
        console.print(
            f"[yellow]Plot '{name}' not found. Let's write a new script.[/yellow]"
        )
        prompt = console.input(
            "[bold magenta]Describe the story premise or genre > [/bold magenta]"
        )

        with console.status(
            "[bold magenta]The Scriptwriter is drafting the episode...[/bold magenta]",
            spinner="bouncingBall",
        ):
            # Pass world to the generator
            plot = await generate_plot(prompt, world)
            plot.id = name
        save_plot(plot, filename)
        history.append(("user", f"Create plot: {prompt}"))
        history.append(("system", "Script drafted."))

    while True:
        console.clear()
        sidebar = get_plot_sidebar(plot)
        main_view = get_main_view(history, "Scriptwriter")
        console.print(Columns([main_view, sidebar], expand=True, equal=False))

        command = console.input("\n[bold magenta]Command > [/bold magenta]")
        if command.lower() in ["exit", "quit", "q"]:
            break

        with console.status(
            "[bold magenta]Refining script...[/bold magenta]", spinner="dots"
        ):
            try:
                # Pass world to the updater
                plot = await update_plot(plot, command, world)
                save_plot(plot, filename)
                history.append(("user", command))
                changes = f"Cast: {len(plot.available_characters)}"
                history.append(("system", f"Update applied. ({changes})"))
            except Exception as e:
                history.append(("user", command))
                history.append(("system", f"[bold red]Error:[/bold red] {str(e)}"))


# --- COMMANDS ---


@app.command()
def build():
    """
    Architect Mode: Design the static world (factions, locations).
    """
    asyncio.run(build_loop())


@app.command()
def plot(name: str):
    """
    Scriptwriter Mode: Design a narrative episode (plot, cast, goal).
    Example: dungen plot heist_mission
    """
    asyncio.run(plot_loop(name))


# --- SESSION MANAGEMENT ---


def get_save_path(session_id: str) -> str:
    """Returns the directory path for a specific session."""
    return os.path.join(SAVES_DIR, session_id)


def save_game(state: GameState, ledger: Ledger):
    """Saves the dynamic session state and history."""
    path = get_save_path(state.session_id)
    os.makedirs(path, exist_ok=True)

    with open(os.path.join(path, "state.yaml"), "w") as f:
        yaml.dump(state.model_dump(), f, sort_keys=False)

    with open(os.path.join(path, "ledger.yaml"), "w") as f:
        yaml.dump(ledger.model_dump(), f, sort_keys=False)


def load_game(session_id: str) -> Optional[Tuple[GameState, Ledger]]:
    """Loads a saved game if it exists."""
    path = get_save_path(session_id)
    if not os.path.exists(path):
        return None

    try:
        with open(os.path.join(path, "state.yaml"), "r") as f:
            state = GameState(**yaml.safe_load(f))

        with open(os.path.join(path, "ledger.yaml"), "r") as f:
            ledger = Ledger(**yaml.safe_load(f))

        return state, ledger
    except Exception as e:
        console.print(f"[bold red]Error loading save:[/bold red] {e}")
        return None


def initialize_session(
    world: World, plot: Plot, player_char: Character, session_id: str
) -> Tuple[GameState, Ledger]:
    """Sets up the initial state, spawning characters in the starting location."""

    actors = {}

    # 1. Spawn Player
    player_state = ActorState(
        id=player_char.id,
        location_id=plot.starting_location_id,
        current_health=1.0,
        status_effects=[],
        inventory=[],
        relationships={},
    )
    actors[player_char.id] = player_state

    # 2. Spawn other Cast Members (NPCs)
    # For V0, we spawn everyone in the starting location so there is immediate interaction.
    for char in plot.available_characters:
        if char.id != player_char.id:
            npc_state = ActorState(
                id=char.id,
                location_id=plot.starting_location_id,
                current_health=1.0,
                status_effects=[],
                relationships={},
            )
            actors[char.id] = npc_state

    # 3. Create State
    state = GameState(
        session_id=session_id,
        turn_count=0,
        current_plot_id=plot.id,
        current_node_id=plot.starting_node_id,
        player_id=player_char.id,
        actors=actors,
        world_flags={},
    )

    # 4. Create Ledger
    ledger = Ledger(events=[])

    return state, ledger


# --- UI COMPONENTS FOR PLAY MODE ---


def get_hud(world: World, state: GameState, plot: Plot) -> Panel:
    """Heads Up Display showing status and location."""

    # Location Info
    loc = world.get_location(state.current_location_id)
    loc_name = loc.name if loc else "Unknown Location"

    # Node Info (The Narrative Vibe)
    node = plot.get_node(state.current_node_id)
    node_title = node.title if node else "Unknown Chapter"

    # Player Status
    player = state.player
    hp_percent = int(player.current_health * 100)
    hp_color = "green" if hp_percent > 50 else "red"
    hp_bar = f"[{hp_color}]{hp_percent}% HP[/{hp_color}]"

    # Status Effects
    effects = ", ".join(player.status_effects) if player.status_effects else "Normal"

    # Grid Layout
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column(justify="right")

    grid.add_row(
        f"[bold cyan]{loc_name}[/bold cyan]",
        f"[bold magenta]{node_title}[/bold magenta]",
    )
    grid.add_row(f"[dim]Turn {state.turn_count}[/dim]", f"{hp_bar} | {effects}")

    return Panel(grid, style="white on black", box=box.HEAVY_EDGE)


def get_scene_view(resolution: Optional[SceneResolution], ledger: Ledger) -> Panel:
    """Renders the main narrative prose."""
    if resolution:
        # Show the latest result from the Director
        text = resolution.narrative_prose
    elif ledger.events:
        # Show the last recorded event if loading a game
        text = ledger.events[-1].narrative_outcome
    else:
        text = "[italic]The story begins...[/italic]"

    return Panel(Markdown(text), title="Chronicle", border_style="cyan", padding=(1, 2))


# --- THE PLAY LOOP ---


async def play_loop(
    session_id: str, new_game: bool = False, plot_name: str = None, char_id: str = None
):
    """The Director Mode REPL."""

    # 1. Load World Context
    world = load_world()
    if not world:
        console.print("[red]No world found. Run 'dungen build' first.[/red]")
        return

    # 2. Initialize or Load Session
    if new_game:
        if not plot_name or not char_id:
            console.print(
                "[red]Error: New games require --plot and --character arguments.[/red]"
            )
            return

        plot = load_plot(f"{plot_name}.yaml")
        if not plot:
            console.print(f"[red]Plot '{plot_name}' not found.[/red]")
            return

        # Find character definition
        player_char = next(
            (c for c in plot.available_characters if c.id == char_id), None
        )
        if not player_char:
            console.print(f"[red]Character '{char_id}' not found in plot.[/red]")
            return

        with console.status("[bold blue]Setting up the simulation...[/bold blue]"):
            state, ledger = initialize_session(world, plot, player_char, session_id)
            save_game(state, ledger)
            console.print(f"[green]New session '{session_id}' initialized.[/green]")
            time.sleep(1)
    else:
        loaded = load_game(session_id)
        if not loaded:
            console.print(f"[red]Session '{session_id}' not found.[/red]")
            return
        state, ledger = loaded
        plot = load_plot(f"{state.current_plot_id}.yaml")

    # 3. Main Loop
    last_resolution = None

    while True:
        console.clear()

        # Render
        hud = get_hud(world, state, plot)
        scene = get_scene_view(last_resolution, ledger)

        console.print(hud)
        console.print(scene)

        # Input
        action = console.input("\n[bold green]What do you do? > [/bold green]")
        if action.lower() in ["quit", "exit"]:
            save_game(state, ledger)
            console.print("[bold green]Game saved. Goodbye.[/bold green]")
            break

        # Simulation Step
        with console.status(
            "[bold magenta]The Director is resolving the scene...[/bold magenta]",
            spinner="aesthetic",
        ):
            try:
                # 0. Prepare History Context
                # We fetch the last 10 events that happened in the current location/scene
                # to give the LLM conversation context.
                recent_history = [
                    e for e in ledger.events
                    if e.location_id == state.current_location_id
                ][-10:]

                # A. Call the LLM with History
                resolution = await resolve_scene(world, plot, state, action, recent_history)
                last_resolution = resolution

                # A. Call the LLM
                resolution = await resolve_scene(world, plot, state, action, recent_history)
                last_resolution = resolution

                # B. Apply Updates
                for update in resolution.updates:
                    if update.target_id == "WORLD":
                        # Handle global flags
                        state.world_flags[update.field] = update.value
                    elif update.target_id in state.actors:
                        # Handle actor updates (health, location, etc.)
                        actor = state.actors[update.target_id]
                        if hasattr(actor, update.field):
                            setattr(actor, update.field, update.value)

                # C. Update Narrative Flow
                state.current_node_id = resolution.next_node_id
                state.turn_count += 1

                # D. Log to Ledger
                # Convert updates to simple strings for the log
                mech_updates = [
                    f"{u.target_id}.{u.field}={u.value}" for u in resolution.updates
                ]

                event = Event(
                    turn=state.turn_count,
                    location_id=state.current_location_id,
                    node_id=state.current_node_id,
                    actor_ids=list(state.actors.keys()),
                    player_action=action,
                    narrative_outcome=resolution.narrative_prose,
                    mechanical_updates=mech_updates,
                )
                ledger.events.append(event)

                # E. Auto-Save
                save_game(state, ledger)

            except Exception as e:
                console.print(f"[bold red]Simulation Error:[/bold red] {e}")
                console.input("[Press Enter to continue]")


@app.command()
def play(
    session: str = typer.Option("default", help="Session ID to save/load"),
    new: bool = typer.Option(False, "--new", "-n", help="Start a new game"),
    plot: str = typer.Option(None, help="Plot ID (required for new game)"),
    character: str = typer.Option(None, help="Character ID (required for new game)"),
):
    """
    Director Mode: Play the game.

    Resume default:
      dungen play

    Start new game:
      dungen play --new --session my_save --plot heist --character vance
    """
    asyncio.run(play_loop(session, new, plot, character))


if __name__ == "__main__":
    app()
