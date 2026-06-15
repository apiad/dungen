"""Murder Mystery — demonstrates the full dungen public API.

Two characters (detective, suspect) take turns over 3 rounds.
All engines are DeterministicEngine — no LLM or API key needed.

Run with:
    uv run python examples/murder_mystery.py
"""

import asyncio

from dungen import (
    ActionCommitted,
    DeterministicEngine,
    Entity,
    Event,
    Simulation,
    SimulationEnded,
    TurnResolved,
    TurnStarted,
    World,
)


# ---------------------------------------------------------------------------
# Entity subclasses
# ---------------------------------------------------------------------------


class Detective(Entity):
    """A detective investigating a crime."""

    def __init__(self, id: str) -> None:
        # questions_asked tracks how many questions the detective has posed
        super().__init__(id, role="detective", accusations=0, case_closed=False, questions_asked=0)
        self.engine = DeterministicEngine(self._decide)

    def _decide(self, character, perception):
        from dungen import ActionCall

        questions_asked = perception.get("questions_asked", 0)
        if questions_asked == 0:
            return ActionCall("question", {"topic": "whereabouts"})
        elif questions_asked == 1:
            return ActionCall("question", {"topic": "motive"})
        else:
            return ActionCall("accuse", {"suspect_id": "prof_plum"})


class Suspect(Entity):
    """A suspect being questioned."""

    def __init__(self, id: str, guilty: bool = False) -> None:
        super().__init__(id, role="suspect", guilty=guilty, confessed=False)
        self.engine = DeterministicEngine(self._decide)
        self._guilty = guilty

    def _decide(self, character, perception):
        from dungen import ActionCall

        # If accused and actually guilty, confess
        if self._guilty and perception.get("accused", False):
            return ActionCall("confess", {})
        return ActionCall("deny", {"claim": "I was at the library all evening"})

    def perceive_fn(self, character, snapshot):
        """Custom perception: include current state plus turn info."""
        state = snapshot.state(character.id)
        return state


# ---------------------------------------------------------------------------
# World setup
# ---------------------------------------------------------------------------

world = World()

detective = Detective("inspector_cole")
suspect = Suspect("prof_plum", guilty=True)

world.register(detective)
world.register(suspect)

# Connect detective to suspect in the scene graph
world.graph.add_edge("inspector_cole", "prof_plum", relation="questioning")


# ---------------------------------------------------------------------------
# Action definitions
# ---------------------------------------------------------------------------


@world.action(commits=True)
def question(actor_id: str, ctx, topic: str) -> dict:
    """Ask the suspect about a specific topic. Records the exchange in the ledger."""
    suspect_id = "prof_plum"
    suspect_state = ctx.state(suspect_id)
    guilty = suspect_state.get("guilty", False)

    # The answer depends on whether the suspect is guilty
    answer = (
        f"I... I was home that night, I swear." if guilty
        else f"I was at the library studying topology."
    )

    # Track how many questions the detective has asked
    questions_asked = ctx.state(actor_id).get("questions_asked", 0)
    ctx.set_state(actor_id, "questions_asked", questions_asked + 1)

    ctx.log(Event(
        turn=ctx.turn,
        actor_id=actor_id,
        action="question",
        args={"topic": topic},
        result={"answer": answer, "topic": topic},
        perceived_by=[actor_id, suspect_id],
    ))

    return {"answer": answer}


@world.action(commits=True)
def accuse(actor_id: str, ctx, suspect_id: str) -> dict:
    """Formally accuse a suspect. If guilty, closes the case."""
    suspect_state = ctx.state(suspect_id)
    guilty = suspect_state.get("guilty", False)

    ctx.set_state(actor_id, "accusations", ctx.state(actor_id)["accusations"] + 1)

    if guilty:
        ctx.set_state(actor_id, "case_closed", True)
        ctx.set_state(suspect_id, "accused", True)

    outcome = "correct" if guilty else "wrong"
    ctx.log(Event(
        turn=ctx.turn,
        actor_id=actor_id,
        action="accuse",
        args={"suspect_id": suspect_id},
        result={"outcome": outcome, "guilty": guilty},
        perceived_by=[actor_id, suspect_id],
    ))

    return {"outcome": outcome}


@world.action(commits=True)
def confess(actor_id: str, ctx) -> dict:
    """Confess to the crime."""
    ctx.set_state(actor_id, "confessed", True)

    ctx.log(Event(
        turn=ctx.turn,
        actor_id=actor_id,
        action="confess",
        args={},
        result={"statement": "It was I who did it. I had no choice."},
        perceived_by=[actor_id, "inspector_cole"],
    ))

    return {"statement": "It was I who did it."}


@world.action(commits=True)
def deny(actor_id: str, ctx, claim: str) -> dict:
    """Deny involvement."""
    ctx.log(Event(
        turn=ctx.turn,
        actor_id=actor_id,
        action="deny",
        args={"claim": claim},
        result={"denial": claim},
        perceived_by=[actor_id, "inspector_cole"],
    ))

    return {"denial": claim}


# ---------------------------------------------------------------------------
# Custom perception for detective (injects turn number)
# ---------------------------------------------------------------------------


def detective_perceive(character, snapshot):
    state = snapshot.state(character.id)
    # Inject a synthetic turn counter so the engine can branch on it
    # (in a real scenario this would come from world state or a hook)
    state = dict(state)
    return state


detective.perceive_fn = detective_perceive  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


async def main():
    sim = Simulation(
        world=world,
        characters=[detective, suspect],
        turn_order="sequential",  # suspect sees detective's accusation in same turn
    )

    print("=== Murder Mystery Simulation ===\n")

    async for event in sim.run(max_turns=3):
        match event:
            case TurnStarted(turn=t):
                print(f"\n-- Turn {t} --")

            case TurnResolved(turn=t, committed=committed):
                for ac in committed:
                    print(f"  [{ac.actor_id}] {ac.action}({ac.args}) → {ac.result}")

            case SimulationEnded(reason=reason):
                print(f"\n=== Simulation ended: {reason} ===")

    # ---------------------------------------------------------------------------
    # POV export
    # ---------------------------------------------------------------------------

    print("\n=== Inspector Cole's case notes (POV export) ===")
    for entry in world.ledger.export_pov("inspector_cole"):
        print(f"  Turn {entry.turn}: {entry.action} → {entry.result}")

    print("\n=== Prof. Plum's perspective ===")
    for entry in world.ledger.export_pov("prof_plum"):
        print(f"  Turn {entry.turn}: {entry.action} → {entry.result}")

    print("\n=== Final state ===")
    print(f"  Case closed: {detective.state.snapshot()['case_closed']}")
    print(f"  Suspect confessed: {suspect.state.snapshot()['confessed']}")


if __name__ == "__main__":
    asyncio.run(main())
