# Copyright 2026 Nearby Computing S.L.
"""The telemetry source must produce a signal worth reacting to."""

import pytest

from ue_simulator import config
from ue_simulator.simulator import RanSimulator


def test_default_topology_parses(monkeypatch):
    monkeypatch.delenv("TOPOLOGY", raising=False)
    assert config.topology() == {"edge1": ["A", "B", "C"], "edge2": ["D", "E"]}


def test_custom_topology(monkeypatch):
    monkeypatch.setenv("TOPOLOGY", "e1=X;e2=Y,Z")
    assert config.topology() == {"e1": ["X"], "e2": ["Y", "Z"]}


@pytest.mark.parametrize("raw", ["", "garbage", "edge1=", "=A,B"])
def test_bad_topology_is_rejected(monkeypatch, raw):
    monkeypatch.setenv("TOPOLOGY", raw)
    with pytest.raises(ValueError):
        config.topology()


def test_cycle_returns_to_idle():
    sim = RanSimulator(seed=1)
    sim.run(max_cycles=1, interval=0)
    assert all(v["users"] == 0 for v in sim.totals().values())
    assert sim.cycles == 1


def test_ramp_up_saturates_then_drains():
    sim = RanSimulator(seed=1)
    steps = max(1, config.RAMP_PERIOD // max(1, config.STEP_SIZE))

    sim._phase("ramp-up", steps, lambda: sim._adjust(1, 4, +1), interval=0)
    peak = sim.totals()
    assert peak["edge1"]["users"] > 0 and peak["edge2"]["users"] > 0
    assert peak["edge1"]["data_rate_mbps"] > 0

    sim._phase("ramp-down", steps, lambda: sim._adjust(1, 4, -1), interval=0)
    assert all(v["users"] == 0 for v in sim.totals().values())


def test_users_never_exceed_the_cell_cap():
    sim = RanSimulator(seed=3)
    for _ in range(200):
        sim._adjust(1, 4, +1)
    assert all(u <= config.MAX_USERS_PER_CELL for u in sim.users.values())


def test_users_never_go_negative():
    sim = RanSimulator(seed=3)
    for _ in range(200):
        sim._adjust(1, 4, -1)
    assert all(u >= 0 for u in sim.users.values())


def test_traffic_is_zero_exactly_when_there_are_no_users():
    sim = RanSimulator(seed=5)
    for _ in range(30):
        sim._adjust(1, 4, +1)
    for cell in sim.cells:
        assert (sim.data_rates[cell] > 0) == (sim.users[cell] > 0)


def test_history_is_bounded(monkeypatch):
    """A long-lived pod must not accumulate samples forever."""
    monkeypatch.setattr(config, "HISTORY_LIMIT", 10)
    sim = RanSimulator(seed=1)
    for _ in range(200):
        sim.publish()
    assert all(len(v) <= 10 for v in sim.history.values())


def test_seed_makes_runs_reproducible():
    a = RanSimulator(seed=42)
    b = RanSimulator(seed=42)
    for sim in (a, b):
        sim._phase("ramp-up", 5, lambda s=sim: s._adjust(1, 4, +1), interval=0)
    assert a.totals() == b.totals()
