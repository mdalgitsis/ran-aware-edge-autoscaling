# Copyright 2026 Nearby Computing S.L.
"""Read the RAN signals from Prometheus.

A failed query returns no samples rather than a zero. The distinction matters:
zero users means "undeploy this application", so silently turning a scrape
failure into a zero would tear down a healthy workload because a monitoring
endpoint blinked.
"""

from __future__ import annotations

import logging

import requests

from autoscaler import config

log = logging.getLogger(__name__)


class PrometheusUnavailable(RuntimeError):
    """Raised when the query could not be answered at all."""


def instant_query(query: str, url: str | None = None) -> dict[str, float]:
    """Run an instant query, returning {edge_node: value}.

    Samples without the edge label are dropped -- they cannot be attributed to
    an edge node, so acting on them would mean acting on the wrong one.
    """
    url = url or config.PROMETHEUS_URL
    try:
        response = requests.get(
            f"{url}/api/v1/query",
            params={"query": query},
            timeout=config.PROMETHEUS_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.RequestException as exc:
        raise PrometheusUnavailable(f"query {query!r} failed: {exc}") from exc
    except ValueError as exc:
        raise PrometheusUnavailable(f"query {query!r} returned non-JSON") from exc

    if payload.get("status") != "success":
        raise PrometheusUnavailable(
            f"query {query!r} returned status {payload.get('status')!r}"
        )

    results: dict[str, float] = {}
    for sample in payload.get("data", {}).get("result", []):
        edge = sample.get("metric", {}).get(config.EDGE_LABEL)
        if not edge:
            log.debug("Dropping sample without %s label", config.EDGE_LABEL)
            continue
        try:
            results[edge] = float(sample["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            log.warning("Unparseable sample for edge %s", edge)
    return results
