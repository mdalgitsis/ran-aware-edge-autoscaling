# Copyright 2026 Nearby Computing S.L.
"""Loop behaviour, especially what it does when its inputs fail."""

import pytest

from autoscaler import controller as controller_module
from autoscaler.controller import RanAwareAutoscaler
from autoscaler.k8s import WorkloadState
from autoscaler.policy import Action
from autoscaler.prometheus import PrometheusUnavailable


class FakeScaler:
    def __init__(self, state=None):
        self.state = state or {}
        self.calls = []

    def get(self, name):
        replicas = self.state.get(name, 0)
        return WorkloadState(exists=name in self.state, replicas=replicas)

    def scale(self, name, replicas):
        self.calls.append((name, replicas))
        self.state[name] = replicas


@pytest.fixture
def scaler():
    return FakeScaler()


def patch_queries(monkeypatch, users, traffic, fail=False):
    def fake_query(query, url=None):
        if fail:
            raise PrometheusUnavailable("scrape failed")
        if query == "cn_active_users_per_edge":
            return users
        return traffic

    monkeypatch.setattr(controller_module, "instant_query", fake_query)


def test_scales_out_on_traffic(monkeypatch, scaler):
    scaler.state["edge-app-edge1"] = 1
    patch_queries(monkeypatch, {"edge1": 40}, {"edge1": 317})
    decisions = RanAwareAutoscaler(scaler=scaler).reconcile_once()
    assert decisions[0].action is Action.SCALE
    assert scaler.calls == [("edge-app-edge1", 7)]


def test_undeploys_when_cells_drain(monkeypatch, scaler):
    scaler.state["edge-app-edge1"] = 4
    patch_queries(monkeypatch, {"edge1": 0}, {"edge1": 0})
    decisions = RanAwareAutoscaler(scaler=scaler).reconcile_once()
    assert decisions[0].action is Action.UNDEPLOY
    assert scaler.calls == [("edge-app-edge1", 0)]


def test_prometheus_failure_holds_position(monkeypatch, scaler):
    """The bug this guards: a scrape failure must not read as zero users.

    Zero users means undeploy. If an unreachable Prometheus were treated as
    zero, one monitoring blip would tear down every workload in the zone.
    """
    scaler.state["edge-app-edge1"] = 4
    patch_queries(monkeypatch, {}, {}, fail=True)
    decisions = RanAwareAutoscaler(scaler=scaler).reconcile_once()
    assert decisions == []
    assert scaler.calls == [], "must not touch the cluster on a failed scrape"
    assert scaler.state["edge-app-edge1"] == 4


def test_one_failing_edge_does_not_block_the_others(monkeypatch):
    class PartlyBrokenScaler(FakeScaler):
        def scale(self, name, replicas):
            if "edge1" in name:
                raise RuntimeError("API server said no")
            super().scale(name, replicas)

    scaler = PartlyBrokenScaler({"edge-app-edge1": 1, "edge-app-edge2": 1})
    patch_queries(
        monkeypatch, {"edge1": 40, "edge2": 40}, {"edge1": 317, "edge2": 317}
    )
    RanAwareAutoscaler(scaler=scaler).reconcile_once()
    assert scaler.calls == [("edge-app-edge2", 7)], "edge2 must still be scaled"


def test_edges_seen_only_in_one_query_are_still_handled(monkeypatch, scaler):
    scaler.state["edge-app-edge2"] = 1
    patch_queries(monkeypatch, {"edge1": 5}, {"edge2": 100})
    decisions = RanAwareAutoscaler(scaler=scaler).reconcile_once()
    assert {d.edge_node for d in decisions} == {"edge1", "edge2"}


def test_bounded_run(monkeypatch, scaler):
    patch_queries(monkeypatch, {"edge1": 0}, {"edge1": 0})
    autoscaler = RanAwareAutoscaler(scaler=scaler)
    autoscaler.run(interval=0, max_iterations=4)
    assert autoscaler.iterations == 4


def test_zero_interval_is_honoured(monkeypatch, scaler):
    """`interval or default` would turn an explicit 0 into the default."""
    patch_queries(monkeypatch, {"edge1": 0}, {"edge1": 0})
    autoscaler = RanAwareAutoscaler(scaler=scaler)
    import time

    started = time.monotonic()
    autoscaler.run(interval=0, max_iterations=3)
    assert time.monotonic() - started < 1.0
