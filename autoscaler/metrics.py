# Copyright 2026 Nearby Computing S.L.
"""What the autoscaler itself exports, so the controller is observable.

A controller that acts on metrics but exports none of its own is impossible to
debug: you can see the input and the cluster, but not what it decided or why.
"""

from prometheus_client import Counter, Gauge

PREFIX = "ran_autoscaler"

desired_replicas = Gauge(
    f"{PREFIX}_desired_replicas",
    "Replicas the policy last asked for on this edge node",
    ["edge_node"],
)
current_replicas = Gauge(
    f"{PREFIX}_current_replicas",
    "Replicas observed on this edge node",
    ["edge_node"],
)
observed_users = Gauge(
    f"{PREFIX}_observed_users",
    "Active users the policy last saw on this edge node",
    ["edge_node"],
)
observed_traffic = Gauge(
    f"{PREFIX}_observed_traffic_mbps",
    "Radio traffic the policy last saw on this edge node, in Mbps",
    ["edge_node"],
)
actions = Counter(
    f"{PREFIX}_actions_total",
    "Decisions taken, by action",
    ["edge_node", "action"],
)
reconcile_errors = Counter(
    f"{PREFIX}_reconcile_errors_total",
    "Reconcile ticks that failed, by cause",
    ["cause"],
)
iterations = Gauge(
    f"{PREFIX}_iterations",
    "Reconcile ticks completed",
)
