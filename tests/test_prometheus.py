# Copyright 2026 Nearby Computing S.L.
"""Parsing Prometheus responses, including the ones that are not answers."""

import pytest

from autoscaler import prometheus
from autoscaler.prometheus import PrometheusUnavailable, instant_query


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"{self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def patch_get(monkeypatch, response):
    def fake_get(*_args, **_kwargs):
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(prometheus.requests, "get", fake_get)


def test_parses_samples_by_edge(monkeypatch):
    patch_get(
        monkeypatch,
        FakeResponse(
            {
                "status": "success",
                "data": {
                    "result": [
                        {"metric": {"edge_node": "edge1"}, "value": [0, "42"]},
                        {"metric": {"edge_node": "edge2"}, "value": [0, "7.5"]},
                    ]
                },
            }
        ),
    )
    assert instant_query("q") == {"edge1": 42.0, "edge2": 7.5}


def test_samples_without_an_edge_label_are_dropped(monkeypatch):
    patch_get(
        monkeypatch,
        FakeResponse(
            {
                "status": "success",
                "data": {
                    "result": [
                        {"metric": {}, "value": [0, "99"]},
                        {"metric": {"edge_node": "edge1"}, "value": [0, "1"]},
                    ]
                },
            }
        ),
    )
    assert instant_query("q") == {"edge1": 1.0}


def test_unparseable_value_is_skipped_not_fatal(monkeypatch):
    patch_get(
        monkeypatch,
        FakeResponse(
            {
                "status": "success",
                "data": {
                    "result": [
                        {"metric": {"edge_node": "edge1"}, "value": [0, "NaNsense"]},
                        {"metric": {"edge_node": "edge2"}, "value": [0, "3"]},
                    ]
                },
            }
        ),
    )
    assert instant_query("q") == {"edge2": 3.0}


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse({"status": "error", "data": {}}),
        FakeResponse(None),
        FakeResponse({}, status=503),
    ],
)
def test_bad_responses_raise_rather_than_returning_empty(monkeypatch, response):
    """Returning {} would read as 'no users' and undeploy everything."""
    patch_get(monkeypatch, response)
    with pytest.raises(PrometheusUnavailable):
        instant_query("q")


def test_connection_error_raises(monkeypatch):
    import requests

    patch_get(monkeypatch, requests.exceptions.ConnectionError("refused"))
    with pytest.raises(PrometheusUnavailable):
        instant_query("q")
