# Copyright 2026 Nearby Computing S.L.
"""The RAN-aware scaling decision, as a pure function.

This is the algorithm from the paper, and it is deliberately free of I/O: it
takes an observation and returns a decision. Everything that can fail --
Prometheus, the Kubernetes API -- lives outside, so the logic that matters can
be tested exhaustively without either.

The rule, in one paragraph: an edge node with no attached users should not be
running the application at all, so undeploy it. An edge node with users should
be running it, sized to the radio traffic those users generate -- desired
replicas is the traffic divided by what one replica is specified to handle,
rounded up. Presence drives deployment; traffic drives scale.

Scaling on *radio* traffic rather than CPU is the whole point. CPU tells you
that load already arrived and the replicas are struggling. The radio tells you
how much is attached right now, before it reaches the application.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    NONE = "none"
    DEPLOY = "deploy"
    UNDEPLOY = "undeploy"
    SCALE = "scale"


@dataclass(frozen=True)
class Observation:
    """What the loop knows about one edge node this tick."""

    edge_node: str
    #: attached subscriber sessions -- core network signal, drives HSIA
    active_users: int
    #: aggregated radio traffic in Mbps -- RAN signal, drives HSRA
    data_rate_mbps: float
    deployed: bool
    current_replicas: int


@dataclass(frozen=True)
class Decision:
    action: Action
    edge_node: str
    target_replicas: int
    reason: str


def decide(
    observation: Observation,
    optimal_traffic_mbps: float,
    min_replicas: int = 1,
    max_replicas: int = 10,
    deadband: int = 0,
) -> Decision:
    """Choose what to do with one edge node.

    ``optimal_traffic_mbps`` is the traffic a single replica is specified to
    serve -- an SLA input, not a measurement.

    ``deadband`` suppresses changes smaller than N replicas. It defaults to 0,
    which is the published algorithm exactly. Any non-zero value is a
    deliberate departure: useful in production, where demand hovering at a
    replica boundary otherwise scales back and forth every tick, but it is not
    what the paper evaluated.
    """
    if optimal_traffic_mbps <= 0:
        raise ValueError("optimal_traffic_mbps must be positive")
    if min_replicas < 1:
        raise ValueError("min_replicas must be at least 1")
    if max_replicas < min_replicas:
        raise ValueError("max_replicas must be >= min_replicas")

    edge = observation.edge_node

    # No users attached: the application has nothing to serve here.
    if observation.active_users <= 0:
        if observation.deployed:
            return Decision(
                Action.UNDEPLOY, edge, 0, "no active users on this edge node"
            )
        return Decision(Action.NONE, edge, 0, "no active users, not deployed")

    # Users attached but nothing running: deploy at the floor and let the next
    # tick size it. Sizing on the same tick would act on traffic measured
    # before the application existed.
    if not observation.deployed:
        return Decision(
            Action.DEPLOY,
            edge,
            min_replicas,
            f"{observation.active_users} active user(s), not deployed",
        )

    desired = math.ceil(observation.data_rate_mbps / optimal_traffic_mbps)
    desired = max(min_replicas, min(max_replicas, desired))

    delta = desired - observation.current_replicas
    if delta == 0 or abs(delta) <= deadband:
        return Decision(
            Action.NONE,
            edge,
            observation.current_replicas,
            f"{observation.data_rate_mbps:.1f} Mbps needs {desired} replica(s); "
            f"already at {observation.current_replicas}",
        )

    direction = "up" if delta > 0 else "down"
    return Decision(
        Action.SCALE,
        edge,
        desired,
        f"{observation.data_rate_mbps:.1f} Mbps needs {desired} replica(s); "
        f"scaling {direction} from {observation.current_replicas}",
    )
