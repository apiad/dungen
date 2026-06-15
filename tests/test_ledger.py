import pytest
from dungen.ledger import Event, Ledger


def make_event(**kwargs) -> Event:
    defaults = dict(
        turn=1,
        actor_id="velun",
        action="move",
        args={},
        result={},
        perceived_by=["velun"],
        seeded=False,
    )
    defaults.update(kwargs)
    return Event(**defaults)


# --- append + export_all ---

def test_export_all_empty():
    ledger = Ledger()
    assert ledger.export_all() == []


def test_append_and_export_all_order():
    ledger = Ledger()
    e1 = make_event(turn=1, actor_id="velun", action="move")
    e2 = make_event(turn=2, actor_id="lys", action="attack")
    e3 = make_event(turn=3, actor_id="velun", action="rest")
    ledger.append(e1)
    ledger.append(e2)
    ledger.append(e3)
    result = ledger.export_all()
    assert result == [e1, e2, e3]


def test_export_all_returns_copy():
    ledger = Ledger()
    e = make_event()
    ledger.append(e)
    result = ledger.export_all()
    result.pop()
    # internal list should be unaffected
    assert len(ledger.export_all()) == 1


# --- query by scalar fields ---

def test_query_by_actor_id():
    ledger = Ledger()
    e1 = make_event(actor_id="velun", turn=1)
    e2 = make_event(actor_id="lys", turn=2)
    e3 = make_event(actor_id="velun", turn=3)
    for e in (e1, e2, e3):
        ledger.append(e)
    assert ledger.query(actor_id="velun") == [e1, e3]
    assert ledger.query(actor_id="lys") == [e2]


def test_query_by_turn():
    ledger = Ledger()
    e1 = make_event(turn=7, actor_id="velun")
    e2 = make_event(turn=8, actor_id="lys")
    e3 = make_event(turn=7, actor_id="nox")
    for e in (e1, e2, e3):
        ledger.append(e)
    assert ledger.query(turn=7) == [e1, e3]
    assert ledger.query(turn=8) == [e2]


def test_query_by_seeded():
    ledger = Ledger()
    e1 = make_event(seeded=True, actor_id="velun")
    e2 = make_event(seeded=False, actor_id="lys")
    e3 = make_event(seeded=True, actor_id="nox")
    for e in (e1, e2, e3):
        ledger.append(e)
    assert ledger.query(seeded=True) == [e1, e3]
    assert ledger.query(seeded=False) == [e2]


def test_query_multiple_filters():
    ledger = Ledger()
    e1 = make_event(actor_id="velun", turn=7)
    e2 = make_event(actor_id="lys", turn=7)
    e3 = make_event(actor_id="velun", turn=8)
    for e in (e1, e2, e3):
        ledger.append(e)
    assert ledger.query(actor_id="velun", turn=7) == [e1]


def test_query_no_match_returns_empty():
    ledger = Ledger()
    ledger.append(make_event(actor_id="velun"))
    assert ledger.query(actor_id="ghost") == []


# --- query by perceived_by (list membership) ---

def test_query_perceived_by_membership():
    ledger = Ledger()
    e1 = make_event(perceived_by=["velun", "lys"])
    e2 = make_event(perceived_by=["lys", "nox"])
    e3 = make_event(perceived_by=["nox"])
    for e in (e1, e2, e3):
        ledger.append(e)
    assert ledger.query(perceived_by="velun") == [e1]
    assert ledger.query(perceived_by="lys") == [e1, e2]
    assert ledger.query(perceived_by="nox") == [e2, e3]


def test_query_perceived_by_not_present():
    ledger = Ledger()
    ledger.append(make_event(perceived_by=["velun"]))
    assert ledger.query(perceived_by="ghost") == []


# --- export_pov ---

def test_export_pov_returns_correct_events():
    ledger = Ledger()
    e1 = make_event(perceived_by=["velun", "lys"], turn=1)
    e2 = make_event(perceived_by=["nox"], turn=2)
    e3 = make_event(perceived_by=["lys"], turn=3)
    for e in (e1, e2, e3):
        ledger.append(e)
    assert ledger.export_pov("lys") == [e1, e3]
    assert ledger.export_pov("nox") == [e2]
    assert ledger.export_pov("velun") == [e1]


def test_export_pov_empty_for_unknown():
    ledger = Ledger()
    ledger.append(make_event(perceived_by=["velun"]))
    assert ledger.export_pov("nobody") == []


def test_export_pov_equals_query_perceived_by():
    ledger = Ledger()
    e1 = make_event(perceived_by=["velun", "lys"])
    e2 = make_event(perceived_by=["lys"])
    for e in (e1, e2):
        ledger.append(e)
    assert ledger.export_pov("lys") == ledger.query(perceived_by="lys")


# --- immutability ---

def test_event_is_frozen():
    e = make_event()
    with pytest.raises(Exception):
        e.turn = 99  # type: ignore[misc]
