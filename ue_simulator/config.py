# Copyright 2026 Nearby Computing S.L.
"""Configuration for the synthetic RAN telemetry source.

Everything is environment-driven. The defaults describe a small two-edge,
five-cell topology, which is the one used in the published evaluation.
"""

from __future__ import annotations

import os

# Which cells (gNBs) are served by which edge node. Format: "edge1=A,B,C;edge2=D,E"
_DEFAULT_TOPOLOGY = "edge1=A,B,C;edge2=D,E"

DATA_RATE_MIN = float(os.getenv("DATA_RATE_MIN", "1"))
DATA_RATE_MAX = float(os.getenv("DATA_RATE_MAX", "10"))

SIMULATION_STEP = float(os.getenv("SIMULATION_STEP", "1"))
IDLE_PERIOD = int(os.getenv("IDLE_PERIOD", "30"))
RAMP_PERIOD = int(os.getenv("RAMP_PERIOD", "30"))
STEP_SIZE = int(os.getenv("STEP_SIZE", "2"))

MAX_USERS_PER_CELL = int(os.getenv("MAX_USERS_PER_CELL", "20"))
USER_INCREMENT_MIN = int(os.getenv("USER_INCREMENT_MIN", "1"))
USER_INCREMENT_MAX = int(os.getenv("USER_INCREMENT_MAX", "4"))
USER_DECREMENT_MIN = int(os.getenv("USER_DECREMENT_MIN", "1"))
USER_DECREMENT_MAX = int(os.getenv("USER_DECREMENT_MAX", "4"))

PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 0 = run forever. A positive value stops after N cycles, used by the smoke test.
MAX_CYCLES = int(os.getenv("MAX_CYCLES", "0"))

# History is kept only to render the optional summary plot. It is bounded
# because this runs as a long-lived pod: the original kept every sample for the
# lifetime of the process, which grows without limit.
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "5000"))
PLOTS_DIR = os.getenv("PLOTS_DIR", "")


def topology() -> dict:
    """Parse TOPOLOGY into {edge_node: [cell, ...]}."""
    raw = os.getenv("TOPOLOGY", _DEFAULT_TOPOLOGY)
    mapping: dict = {}
    for group in raw.split(";"):
        group = group.strip()
        if not group:
            continue
        edge, _, cells = group.partition("=")
        cell_list = [c.strip() for c in cells.split(",") if c.strip()]
        if not edge.strip() or not cell_list:
            raise ValueError(
                f"TOPOLOGY entry {group!r} is not 'edge=cell1,cell2'"
            )
        mapping[edge.strip()] = cell_list
    if not mapping:
        raise ValueError("TOPOLOGY resolved to no edge nodes")
    return mapping
