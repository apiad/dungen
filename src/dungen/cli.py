import typer
import asyncio
import os
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.columns import Columns
from rich.table import Table
from rich.text import Text
from rich import box

# Import from our modules
from dungen.models import World, Plot
from dungen.llm import generate_world, update_world, generate_plot, update_plot

app = typer.Typer(
    no_args_is_help=True,
    name="dungen",
    help="A text-based world builder, roleplay engine, and story generator.",
)
console = Console()

# --- CONSTANTS ---
WORLD_FILE = "world.yaml"
PLOTS_DIR = "plots"


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
        return Panel(welcome_md, title="Activity Log", border_style="white", box=box.ROUNDED)

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
    desc = world.description[:150] + "..." if len(world.description) > 150 else world.description
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
        console.print(Panel("[bold green]dungen: Architect Mode[/bold green]", subtitle="Initialization"))
        console.print("[yellow]No 'world.yaml' found. Let's create a new world.[/yellow]")
        prompt = console.input("[bold green]Describe your world concept > [/bold green]")

        with console.status("[bold green]The Architect is designing the blueprint...[/bold green]", spinner="earth"):
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
    filename = f"{name}.yaml"
    plot = load_plot(filename)
    history = []

    if not plot:
        console.clear()
        console.print(Panel("[bold magenta]dungen: Scriptwriter Mode[/bold magenta]", subtitle="Pre-Production"))
        console.print(f"[yellow]Plot '{name}' not found. Let's write a new script.[/yellow]")
        prompt = console.input("[bold magenta]Describe the story premise or genre > [/bold magenta]")

        with console.status("[bold magenta]The Scriptwriter is drafting the episode...[/bold magenta]", spinner="bouncingBall"):
            plot = await generate_plot(prompt)
            # Ensure the ID matches the filename provided by user for consistency
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

        with console.status("[bold magenta]Refining script...[/bold magenta]", spinner="dots"):
            try:
                plot = await update_plot(plot, command)
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


if __name__ == "__main__":
    app()
