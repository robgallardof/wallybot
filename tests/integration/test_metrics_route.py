import pytest

pytestmark = pytest.mark.integration


def test_metrics_route_needs_no_auth(client) -> None:
    """Prometheus can't hold a session cookie -- this route relies on network isolation
    (blocked at the gateway edge, see docker/gateway.conf) instead of app-level auth."""
    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_metrics_route_exposes_the_http_request_counter(client) -> None:
    client.get("/api/metrics")  # generates at least one HTTP_REQUEST_COMPLETED first

    response = client.get("/api/metrics")

    assert "wallybot_http_requests_total" in response.text
