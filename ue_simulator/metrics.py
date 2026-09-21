# Copyright 2026 Nearby Computing S.L.
"""Prometheus gauges exported by the RAN telemetry source.

These are the signals the autoscaler consumes. Per-cell series carry both the
cell and the edge node that serves it, so a consumer can aggregate either way
without needing the topology itself.
"""

from prometheus_client import Gauge

PREFIX = "ran"

users_per_cell = Gauge(
    f"{PREFIX}_users_per_cell",
    "Active user equipments attached to a cell",
    ["edge_node", "cell_id"],
)
data_rate_per_cell = Gauge(
    f"{PREFIX}_data_rate_per_cell_mbps",
    "Aggregate downlink data rate for a cell, in Mbps",
    ["edge_node", "cell_id"],
)
users_per_edge = Gauge(
    f"{PREFIX}_users_per_edge",
    "Active user equipments served by an edge node",
    ["edge_node"],
)
data_rate_per_edge = Gauge(
    f"{PREFIX}_data_rate_per_edge_mbps",
    "Aggregate downlink data rate for an edge node, in Mbps",
    ["edge_node"],
)
cycle = Gauge(
    f"{PREFIX}_simulation_cycle",
    "Completed idle/ramp-up/ramp-down cycles since start",
)
