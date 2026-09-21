# Copyright 2026 Nearby Computing S.L.
"""Autoscaler configuration. Environment-driven, no baked-in endpoints."""

from __future__ import annotations

import os

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL", "http://prometheus.monitoring.svc.cluster.local:9090"
)
PROMETHEUS_TIMEOUT = int(os.getenv("PROMETHEUS_TIMEOUT", "10"))

# PromQL series produced by the RAN telemetry source.
USERS_QUERY = os.getenv("USERS_QUERY", "cn_active_users_per_edge")
TRAFFIC_QUERY = os.getenv("TRAFFIC_QUERY", "ran_data_rate_per_edge_mbps")
EDGE_LABEL = os.getenv("EDGE_LABEL", "edge_node")

# The workload under control.
NAMESPACE = os.getenv("NAMESPACE", "default")
# Deployment name per edge node, e.g. "edge-app-{edge_node}".
DEPLOYMENT_TEMPLATE = os.getenv("DEPLOYMENT_TEMPLATE", "edge-app-{edge_node}")

# SLA inputs.
OPTIMAL_TRAFFIC_MBPS = float(os.getenv("OPTIMAL_TRAFFIC_MBPS", "50"))
MIN_REPLICAS = int(os.getenv("MIN_REPLICAS", "1"))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", "10"))
# 0 reproduces the published algorithm; >0 suppresses small oscillations.
DEADBAND = int(os.getenv("DEADBAND", "0"))

RECONCILE_INTERVAL = float(os.getenv("RECONCILE_INTERVAL", "10"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "0"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "9110"))

# When true the loop decides and reports but never writes to the cluster.
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
