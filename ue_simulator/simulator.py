# Copyright 2026 Nearby Computing S.L.
"""Synthetic RAN telemetry: users and traffic per cell and per edge node.

Real radio telemetry is the one thing you cannot get on a laptop, and without
it there is nothing to test a RAN-aware orchestrator against. This generates a
plausible substitute and exports it as Prometheus metrics.

Each cycle has three phases, which is what makes the output useful rather than
just noisy:

1. **idle** -- no users. The orchestrator should scale to zero or undeploy.
2. **ramp-up** -- users arrive until cells saturate. Traffic should drive
   scale-out.
3. **ramp-down** -- users leave. Scale-in, then back to idle.

The cycle repeats, so a consumer sees the same transition repeatedly and its
behaviour at each edge is observable rather than a one-off.
"""

from __future__ import annotations

import logging
import random
import signal
import sys
import time
from collections import defaultdict, deque

from prometheus_client import start_http_server

from ue_simulator import config, metrics

log = logging.getLogger(__name__)


class RanSimulator:
    def __init__(self, topology=None, seed: int | None = None):
        self.topology = topology or config.topology()
        self.cells = [c for cells in self.topology.values() for c in cells]
        self._rng = random.Random(seed)

        self.users = dict.fromkeys(self.cells, 0)
        self.data_rates = dict.fromkeys(self.cells, 0.0)
        self.cycles = 0

        # Bounded: this process is long-lived, so unbounded history would be a
        # slow leak rather than a useful record.
        self.history = defaultdict(lambda: deque(maxlen=config.HISTORY_LIMIT))

    # ---- traffic model ---------------------------------------------------

    def _recompute_data_rate(self, cell: str) -> None:
        """Traffic is the sum of per-user demands, so it tracks users with noise."""
        self.data_rates[cell] = sum(
            self._rng.uniform(config.DATA_RATE_MIN, config.DATA_RATE_MAX)
            for _ in range(self.users[cell])
        )

    def _adjust(self, delta_min: int, delta_max: int, sign: int) -> None:
        for cell in self.cells:
            delta = self._rng.randint(delta_min, delta_max) * sign
            self.users[cell] = max(
                0, min(config.MAX_USERS_PER_CELL, self.users[cell] + delta)
            )
            self._recompute_data_rate(cell)

    # ---- export ----------------------------------------------------------

    def publish(self) -> None:
        for edge, cells in self.topology.items():
            edge_users = 0
            edge_rate = 0.0
            for cell in cells:
                metrics.users_per_cell.labels(edge_node=edge, cell_id=cell).set(
                    self.users[cell]
                )
                metrics.data_rate_per_cell.labels(
                    edge_node=edge, cell_id=cell
                ).set(self.data_rates[cell])
                edge_users += self.users[cell]
                edge_rate += self.data_rates[cell]

            metrics.users_per_edge.labels(edge_node=edge).set(edge_users)
            metrics.data_rate_per_edge.labels(edge_node=edge).set(edge_rate)
            self.history[f"users:{edge}"].append(edge_users)
            self.history[f"rate:{edge}"].append(edge_rate)

        for cell in self.cells:
            self.history[f"users:cell:{cell}"].append(self.users[cell])
            self.history[f"rate:cell:{cell}"].append(self.data_rates[cell])

    def totals(self) -> dict:
        return {
            edge: {
                "users": sum(self.users[c] for c in cells),
                "data_rate_mbps": round(sum(self.data_rates[c] for c in cells), 1),
            }
            for edge, cells in self.topology.items()
        }

    # ---- phases ----------------------------------------------------------

    def _phase(self, name: str, steps: int, adjust=None, interval=None) -> None:
        interval = config.SIMULATION_STEP if interval is None else interval
        log.info("Phase: %s", name)
        for _ in range(steps):
            if adjust:
                adjust()
            self.publish()
            if interval:
                time.sleep(interval)
        log.info("  %s -> %s", name, self.totals())

    def run_cycle(self, interval=None) -> None:
        self._phase("idle", config.IDLE_PERIOD, interval=interval)

        steps = max(1, config.RAMP_PERIOD // max(1, config.STEP_SIZE))
        self._phase(
            "ramp-up",
            steps,
            lambda: self._adjust(
                config.USER_INCREMENT_MIN, config.USER_INCREMENT_MAX, +1
            ),
            interval=interval,
        )
        self._phase(
            "ramp-down",
            steps,
            lambda: self._adjust(
                config.USER_DECREMENT_MIN, config.USER_DECREMENT_MAX, -1
            ),
            interval=interval,
        )

        self.cycles += 1
        metrics.cycle.set(self.cycles)

    def run(self, max_cycles=None, interval=None) -> None:
        max_cycles = config.MAX_CYCLES if max_cycles is None else max_cycles
        while True:
            self.run_cycle(interval=interval)
            if max_cycles and self.cycles >= max_cycles:
                log.info("Reached MAX_CYCLES=%s; stopping.", max_cycles)
                return


def _shutdown(_sig, _frame):
    log.info("Shutting down.")
    sys.exit(0)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    simulator = RanSimulator()
    log.info("Topology: %s", simulator.topology)

    start_http_server(config.PROMETHEUS_PORT)
    log.info("Prometheus exporter listening on :%s", config.PROMETHEUS_PORT)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    simulator.run()


if __name__ == "__main__":
    main()
