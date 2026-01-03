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
from dungen.models import World
from dungen.llm import generate_world, update_world

app = typer.Typer(
    no_args_is_help=True,
    name="dungen",
    help="A text-based world builder, roleplay engine, and story generator.",
)
console = Console()
WORLD_FILE = "world.yaml"


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


def get_sidebar(world: World) -> Panel:
    """Generates the side panel showing the current world state."""
    # 1. General Info
    info_text = Text()
    info_text.append(f"{world.name}\n", style="bold cyan underline")
    # Truncate description for UI cleanliness
    desc = world.description
    info_text.append(f"{desc}\n\n", style="italic dim")

    # 2. Locations
    info_text.append("Locations:\n", style="bold green")
    if world.locations:
        for loc in world.locations:
            info_text.append(f"• {loc.name}\n", style="green")
    else:
        info_text.append("• None\n", style="dim")
    info_text.append("\n")

    # 3. Factions
    info_text.append("Factions:\n", style="bold yellow")
    if world.factions:
        for fac in world.factions:
            info_text.append(f"• {fac.name}\n", style="yellow")
    else:
        info_text.append("• None\n", style="dim")

    return Panel(
        info_text,
        title="[bold]Current State[/bold]",
        border_style="blue",
        box=box.ROUNDED,
        padding=(1, 2),
    )


def get_main_view(history: list) -> Panel:
    """Generates the main conversation view."""
    if not history:
        welcome_md = Markdown(
            """
# Welcome, Architect.

The studio is open. You can:
* **Describe** new locations to add.
* **Tweak** faction ideologies.
* **Refine** the world's history.

*Type 'exit' to save and quit.*
            """
        )
        return Panel(welcome_md, title="Activity Log", border_style="white", box=box.ROUNDED)

    # Render the last few history items
    table = Table(box=None, show_header=False, padding=(0, 0, 1, 0))
    table.add_column("Content")

    for role, text in history[-5:]:  # Show last 5 interactions
        if role == "user":
            table.add_row(f"[bold blue]Architect >[/bold blue] {text}")
        else:
            table.add_row(f"[dim]{text}[/dim]")

    return Panel(table, title="Activity Log", border_style="white", box=box.ROUNDED)


async def build_loop():
    """The async loop for the Architect Mode."""

    # 1. Initialization Phase
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

    # 2. Main Edit Loop
    while True:
        console.clear()

        # Render the Layout
        sidebar = get_sidebar(world)
        main_view = get_main_view(history)

        # Use Columns to create the split view
        # Expand=True forces the columns to take up available width
        console.print(Columns([main_view, sidebar], expand=True, equal=False))

        # Input Prompt
        command = console.input("\n[bold blue]Command > [/bold blue]")

        if command.lower() in ["exit", "quit", "q"]:
            console.print("[bold green]World saved. Exiting.[/bold green]")
            break

        # Processing
        with console.status("[bold blue]The Architect is refining the world...[/bold blue]", spinner="dots"):
            try:
                # Pass the current world state to the LLM to get the updated version
                world = await update_world(world, command)
                save_world(world)

                # Update history
                history.append(("user", command))

                # Create a summary of changes for the log
                changes = f"Locations: {len(world.locations)} | Factions: {len(world.factions)}"
                history.append(("system", f"Update applied. ({changes})"))

            except Exception as e:
                history.append(("user", command))
                history.append(("system", f"[bold red]Error:[/bold red] {str(e)}"))


@app.command()
def build():
    """
    Open the Architect interface to design or modify the world.
    """
    asyncio.run(build_loop())


if __name__ == "__main__":
    app()