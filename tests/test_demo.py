# Copyright 2026 Nearby Computing S.L.
"""The end-to-end demo is the repository's claim; it must actually hold."""

from autoscaler.demo import run
from autoscaler.policy import Action


def test_demo_deploys_scales_and_undeploys():
    events, workload = run(cycles=1, quiet=True)
    actions = [d.action for _phase, _edge, d in events]

    assert Action.DEPLOY in actions, "never deployed as users arrived"
    assert Action.SCALE in actions, "never scaled with the traffic ramp"
    assert Action.UNDEPLOY in actions, "never undeployed once cells drained"
    assert all(r == 0 for r in workload.replicas.values()), (
        "replicas left running on idle edge nodes"
    )


def test_replicas_follow_traffic_direction():
    """Scale-out must happen during ramp-up, scale-in during ramp-down."""
    events, _ = run(cycles=1, quiet=True)
    def scales_in(phase_name):
        return [
            d
            for phase, _edge, d in events
            if phase == phase_name and d.action is Action.SCALE
        ]

    up, down = scales_in("ramp-up"), scales_in("ramp-down")
    assert up and down
    assert max(d.target_replicas for d in up) > 1


def test_both_edge_nodes_are_driven():
    events, workload = run(cycles=1, quiet=True)
    assert {e for _p, e, _d in events} == {"edge1", "edge2"}
