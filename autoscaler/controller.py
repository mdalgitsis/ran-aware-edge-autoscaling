# Copyright 2026 Nearby Computing S.L.
"""RAN-aware autoscaling control loop.

Each tick: read users and radio traffic per edge node from Prometheus, read
the current replica count from Kubernetes, ask the policy what to do, and
apply it.

The loop holds no scaling logic of its own -- that all lives in
:mod:`autoscaler.policy` as a pure function. What lives here is everything
that can fail, and the decisions about what to do when it does.

The important one: if Prometheus cannot be reached, the loop does nothing at
all this tick. It does not assume zero users. Zero users means "undeploy", so
treating a scrape failure as zero would tear down every healthy workload the
moment monitoring hiccupped.
"""

from __future__ import annotations

import logging
import signal
import sys
import time

from prometheus_client import start_http_server

from autoscaler import config, metrics
from autoscaler.k8s import DeploymentScaler
from autoscaler.policy import Action, Decision, Observation, decide
from autoscaler.prometheus import PrometheusUnavailable, instant_query

log = logging.getLogger(__name__)


class RanAwareAutoscaler:
    def __init__(self, scaler=None):
        self.scaler = scaler or DeploymentScaler(
            namespace=config.NAMESPACE, dry_run=config.DRY_RUN
        )
        self.iterations = 0

    def deployment_name(self, edge_node: str) -> str:
        return config.DEPLOYMENT_TEMPLATE.format(edge_node=edge_node)

    def observe(self) -> dict:
        """Read the RAN signals. Raises PrometheusUnavailable if it cannot."""
        users = instant_query(config.USERS_QUERY)
        traffic = instant_query(config.TRAFFIC_QUERY)

        observations = {}
        for edge in sorted(set(users) | set(traffic)):
            state = self.scaler.get(self.deployment_name(edge))
            user_count = int(users.get(edge, 0))
            rate = float(traffic.get(edge, 0.0))

            metrics.observed_users.labels(edge_node=edge).set(user_count)
            metrics.observed_traffic.labels(edge_node=edge).set(rate)
            metrics.current_replicas.labels(edge_node=edge).set(state.replicas)

            observations[edge] = Observation(
                edge_node=edge,
                active_users=user_count,
                data_rate_mbps=rate,
                deployed=state.exists and state.replicas > 0,
                current_replicas=state.replicas,
            )
        return observations

    def apply(self, decision: Decision) -> None:
        metrics.actions.labels(
            edge_node=decision.edge_node, action=decision.action.value
        ).inc()
        metrics.desired_replicas.labels(edge_node=decision.edge_node).set(
            decision.target_replicas
        )

        if decision.action is Action.NONE:
            log.debug("%s: %s", decision.edge_node, decision.reason)
            return

        log.info(
            "%s: %s -> %s", decision.edge_node, decision.action.value, decision.reason
        )
        name = self.deployment_name(decision.edge_node)
        self.scaler.scale(name, decision.target_replicas)

    def reconcile_once(self) -> list:
        try:
            observations = self.observe()
        except PrometheusUnavailable as exc:
            # Hold position. See the module docstring for why this is not a
            # "scale everything to zero" path.
            metrics.reconcile_errors.labels(cause="prometheus_unavailable").inc()
            log.error("Holding: %s", exc)
            return []

        decisions = []
        for observation in observations.values():
            decision = decide(
                observation,
                optimal_traffic_mbps=config.OPTIMAL_TRAFFIC_MBPS,
                min_replicas=config.MIN_REPLICAS,
                max_replicas=config.MAX_REPLICAS,
                deadband=config.DEADBAND,
            )
            try:
                self.apply(decision)
            except Exception as exc:  # noqa: BLE001 - one bad edge must not
                # stop the others; a single unreachable Deployment should not
                # freeze scaling across the whole availability zone.
                metrics.reconcile_errors.labels(cause="apply_failed").inc()
                log.error("%s: failed to apply decision: %s", decision.edge_node, exc)
                continue
            decisions.append(decision)
        return decisions

    def run(self, interval=None, max_iterations=None) -> None:
        if interval is None:
            interval = config.RECONCILE_INTERVAL
        if max_iterations is None:
            max_iterations = config.MAX_ITERATIONS

        while True:
            self.iterations += 1
            metrics.iterations.set(self.iterations)
            log.debug("--- reconcile %s ---", self.iterations)
            self.reconcile_once()

            if max_iterations and self.iterations >= max_iterations:
                log.info("Reached MAX_ITERATIONS=%s; stopping.", max_iterations)
                return
            if interval:
                time.sleep(interval)


def _shutdown(_sig, _frame):
    log.info("Shutting down.")
    sys.exit(0)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    if config.DRY_RUN:
        log.warning("DRY_RUN is set: decisions will be logged, not applied.")

    start_http_server(config.METRICS_PORT)
    log.info("Autoscaler metrics on :%s", config.METRICS_PORT)
    log.info(
        "Policy: %.1f Mbps per replica, %s-%s replicas, deadband %s",
        config.OPTIMAL_TRAFFIC_MBPS,
        config.MIN_REPLICAS,
        config.MAX_REPLICAS,
        config.DEADBAND,
    )

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    RanAwareAutoscaler().run()


if __name__ == "__main__":
    main()
