# Copyright 2026 Nearby Computing S.L.
"""Run the whole loop on a laptop: simulator -> policy -> replica decisions.

No cluster, no Prometheus. The RAN telemetry source is driven in-process and
its output handed straight to the policy, with an in-memory stand-in for the
Deployment. It exists so the behaviour this repository is about can be seen in
about ten seconds, without provisioning anything.

What you should see: replicas at zero while the cells are idle, the
application deployed as the first users attach, scale-out tracking the traffic
ramp, then scale-in and undeploy as the cells drain.
"""

from __future__ import annotations

import argparse

from autoscaler.policy import Action, Observation, decide
from ue_simulator import config as ue_config
from ue_simulator.simulator import RanSimulator


class InMemoryWorkload:
    """Stands in for a Deployment, one per edge node."""

    def __init__(self):
        self.replicas = {}

    def get(self, edge: str) -> int:
        return self.replicas.get(edge, 0)

    def apply(self, decision) -> None:
        if decision.action is Action.UNDEPLOY:
            self.replicas[decision.edge_node] = 0
        elif decision.action in (Action.DEPLOY, Action.SCALE):
            self.replicas[decision.edge_node] = decision.target_replicas


def run(cycles: int = 1, optimal_traffic: float = 50.0, quiet: bool = False):
    simulator = RanSimulator(seed=7)
    workload = InMemoryWorkload()
    events = []

    phases = [
        ("idle", ue_config.IDLE_PERIOD, None),
        (
            "ramp-up",
            max(1, ue_config.RAMP_PERIOD // max(1, ue_config.STEP_SIZE)),
            lambda: simulator._adjust(1, 4, +1),
        ),
        (
            "ramp-down",
            max(1, ue_config.RAMP_PERIOD // max(1, ue_config.STEP_SIZE)),
            lambda: simulator._adjust(1, 4, -1),
        ),
    ]

    header = f"{'phase':<11}{'edge':<7}{'users':>6}{'Mbps':>8}{'replicas':>10}  action"
    if not quiet:
        print(header)
        print("-" * len(header))

    for _ in range(cycles):
        for phase_name, steps, adjust in phases:
            for _step in range(steps):
                if adjust:
                    adjust()
                totals = simulator.totals()

                for edge, values in totals.items():
                    observation = Observation(
                        edge_node=edge,
                        active_users=values["users"],
                        data_rate_mbps=values["data_rate_mbps"],
                        deployed=workload.get(edge) > 0,
                        current_replicas=workload.get(edge),
                    )
                    decision = decide(
                        observation, optimal_traffic_mbps=optimal_traffic
                    )
                    workload.apply(decision)

                    if decision.action is not Action.NONE:
                        events.append((phase_name, edge, decision))
                        if not quiet:
                            print(
                                f"{phase_name:<11}{edge:<7}"
                                f"{values['users']:>6}"
                                f"{values['data_rate_mbps']:>8.0f}"
                                f"{workload.get(edge):>10}  "
                                f"{decision.action.value}"
                            )
        simulator.cycles += 1

    return events, workload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local end-to-end demo of RAN-aware autoscaling."
    )
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument(
        "--optimal-traffic",
        type=float,
        default=50.0,
        help="Mbps a single replica is specified to serve.",
    )
    args = parser.parse_args()

    events, workload = run(
        cycles=args.cycles, optimal_traffic=args.optimal_traffic
    )
    print()
    print(f"{len(events)} scaling action(s); final replicas: {workload.replicas}")


if __name__ == "__main__":
    main()
