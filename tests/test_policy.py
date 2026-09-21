# Copyright 2026 Nearby Computing S.L.
"""The scaling policy, which is where every decision actually gets made."""

import dataclasses
import math

import pytest

from autoscaler.policy import Action, Decision, Observation, decide

SLA = 50.0


def obs(users, mbps, deployed, replicas, edge="edge1"):
    return Observation(edge, users, mbps, deployed, replicas)


def test_no_users_undeploys_a_running_app():
    d = decide(obs(0, 0, True, 3), SLA)
    assert d.action is Action.UNDEPLOY
    assert d.target_replicas == 0


def test_no_users_and_nothing_running_does_nothing():
    assert decide(obs(0, 0, False, 0), SLA).action is Action.NONE


def test_users_arriving_deploys_at_the_floor():
    d = decide(obs(5, 30, False, 0), SLA, min_replicas=2)
    assert d.action is Action.DEPLOY
    assert d.target_replicas == 2, "must not size on traffic measured before deploy"


def test_replicas_track_traffic_over_the_sla():
    for mbps, expected in [(1, 1), (50, 1), (51, 2), (100, 2), (317, 7)]:
        d = decide(obs(40, mbps, True, 1), SLA, max_replicas=100)
        assert d.target_replicas == max(1, math.ceil(mbps / SLA)), mbps
        assert d.target_replicas == expected


def test_replicas_are_clamped():
    assert decide(obs(60, 99999, True, 3), SLA, max_replicas=10).target_replicas == 10
    assert decide(obs(1, 0.1, True, 1), SLA, min_replicas=3).target_replicas == 3


def test_no_action_when_already_correct():
    assert decide(obs(20, 150, True, 3), SLA).action is Action.NONE


def test_deadband_suppresses_small_changes():
    """The oscillation visible in the demo at peak load."""
    o = obs(60, 328, True, 6)  # wants 7, currently 6
    assert decide(o, SLA, deadband=0).action is Action.SCALE
    assert decide(o, SLA, deadband=1).action is Action.NONE


def test_deadband_still_allows_large_changes():
    o = obs(60, 500, True, 2)  # wants 10
    assert decide(o, SLA, max_replicas=10, deadband=2).action is Action.SCALE


@pytest.mark.parametrize(
    "kwargs",
    [
        {"optimal_traffic_mbps": 0},
        {"optimal_traffic_mbps": -5},
        {"optimal_traffic_mbps": SLA, "min_replicas": 0},
        {"optimal_traffic_mbps": SLA, "min_replicas": 5, "max_replicas": 2},
    ],
)
def test_invalid_sla_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        decide(obs(10, 100, True, 1), **kwargs)


def test_decision_is_immutable():
    d = decide(obs(10, 100, True, 1), SLA)
    assert isinstance(d, Decision)
    with pytest.raises(dataclasses.FrozenInstanceError):
        d.action = Action.NONE


def test_every_decision_explains_itself():
    for o in [
        obs(0, 0, True, 3),
        obs(0, 0, False, 0),
        obs(5, 30, False, 0),
        obs(40, 317, True, 2),
        obs(20, 150, True, 3),
    ]:
        assert decide(o, SLA).reason, "a decision with no reason is undebuggable"
