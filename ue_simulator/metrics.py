# Copyright 2026 Nearby Computing S.L.
"""Prometheus gauges exported by the telemetry source.

The prefixes are load-bearing, and they are the paper's point.

``cn_`` series are what a **5G core** knows: how many subscribers are attached
and where. In a real deployment these come from core session data, not from
the radio.

``ran_`` series are what the **radio access network** knows: the bitrate each
cell is actually carrying.

The two answer different questions. Session counts say whether an application
needs to exist at an edge node at all; radio traffic says how big it needs to
be. Collapsing them into one "RAN metrics" bucket loses exactly the
distinction the orchestration strategies are built on.

This simulator stands in for both sources at once, because on a laptop there
is neither a core nor a radio.
"""

from prometheus_client import Gauge

# --- core network: subscriber sessions -------------------------------------

active_users_per_cell = Gauge(
    "cn_active_users_per_cell",
    "Attached subscriber sessions, attributed to a cell (core network data)",
    ["edge_node", "cell_id"],
)
active_users_per_edge = Gauge(
    "cn_active_users_per_edge",
    "Attached subscriber sessions served by an edge node (core network data)",
    ["edge_node"],
)

# --- radio access network: carried traffic ---------------------------------

data_rate_per_cell = Gauge(
    "ran_data_rate_per_cell_mbps",
    "Aggregate downlink data rate for a cell, in Mbps (RAN data)",
    ["edge_node", "cell_id"],
)
data_rate_per_edge = Gauge(
    "ran_data_rate_per_edge_mbps",
    "Aggregate downlink data rate for an edge node, in Mbps (RAN data)",
    ["edge_node"],
)

# --- simulator liveness ----------------------------------------------------

cycle = Gauge(
    "ue_simulator_cycle",
    "Completed idle/ramp-up/ramp-down cycles since start",
)
