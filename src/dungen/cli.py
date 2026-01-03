import typer
import asyncio
import os
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

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
        # model_dump() converts Pydantic to a dict
        yaml.dump(world.model_dump(), f, sort_keys=False)


def load_world() -> World | None:
    """Load the World object from YAML if it exists."""
    if not os.path.exists(WORLD_FILE):
        return None
    with open(WORLD_FILE, "r") as f:
        data = yaml.safe_load(f)
    return World(**data)


async def build_loop():
    """The async loop for the Architect Mode."""
    console.print(
        Panel(
            "[bold green]dungen: Architect Mode[/bold green]", subtitle="Worldbuilder"
        )
    )

    # 1. Check for existing world
    world = load_world()

    if world:
        console.print(f"[dim]Loaded existing world: [bold]{world.name}[/bold][/dim]")
        console.print(Markdown(f"*{world.description}*"))
    else:
        # 2. Create new world if none exists
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
        console.print(
            Panel(
                Markdown(f"# {world.name}\n\n{world.description}"),
                title="World Created",
                border_style="green",
            )
        )

    # 3. Enter the Edit Loop
    while True:
        console.print(
            "\n[dim]Enter a command to modify the world (or 'exit' to quit)[/dim]"
        )
        command = console.input("[bold blue]Architect > [/bold blue]")

        if command.lower() in ["exit", "quit", "q"]:
            console.print("[bold green]World saved. Exiting.[/bold green]")
            break

        with console.status(
            "[bold blue]The Architect is refining the world...[/bold blue]",
            spinner="dots",
        ):
            # Pass the current world state to the LLM to get the updated version
            world = await update_world(world, command)

        # Save and show feedback
        save_world(world)
        console.print(
            Panel(
                f"[bold]Updates Applied[/bold]\n\n"
                f"Locations: {len(world.locations)}\n"
                f"Factions: {len(world.factions)}",
                border_style="blue",
            )
        )


@app.command()
def build():
    """
    Open the Architect interface to design or modify the world.
    """
    asyncio.run(build_loop())


if __name__ == "__main__":
    app()
