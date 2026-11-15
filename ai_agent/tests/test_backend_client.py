"""The agent can only read from the backend."""

import pytest

from orbit_agent.backend_client import (
    BackendUnavailable,
    ReadOnlyBackendClient,
    ReadOnlyViolation,
)
from tests.support import BACKEND_URL, NOOR, FakeBackend


def test_reads_use_get_and_are_logged() -> None:
    backend = FakeBackend()
    client = ReadOnlyBackendClient(BACKEND_URL, transport=backend)

    evaluations = client.evaluations(NOOR, "sleep")
    client.baselines(NOOR)
    client.measurements(NOOR)
    client.metrics()

    assert len(evaluations) == 3
    assert {method for method, _ in backend.requests} == {"GET"}
    assert [record.item_count for record in client.access_log] == [3, 7, 171, 15]
    assert client.access_log[0].path == f"/crew-members/{NOOR}/evaluations?domain=sleep"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_write_verbs_are_refused_before_any_request(method: str) -> None:
    backend = FakeBackend()
    client = ReadOnlyBackendClient(BACKEND_URL, transport=backend)

    with pytest.raises(ReadOnlyViolation):
        client._request(method, "/measurements")

    assert backend.requests == []


def test_client_exposes_no_computation_command() -> None:
    public = {name for name in dir(ReadOnlyBackendClient) if not name.startswith("_")}

    assert not {name for name in public if name.startswith(("generate", "create", "post"))}


def test_unreachable_backend_is_reported() -> None:
    client = ReadOnlyBackendClient(BACKEND_URL, transport=FakeBackend(reachable=False))

    with pytest.raises(BackendUnavailable):
        client.evaluations(NOOR)


def test_unexpected_status_is_reported() -> None:
    client = ReadOnlyBackendClient(BACKEND_URL, transport=FakeBackend())

    with pytest.raises(BackendUnavailable, match="404"):
        client._request("GET", "/unknown")


def test_unknown_crew_member_returns_no_items() -> None:
    client = ReadOnlyBackendClient(BACKEND_URL, transport=FakeBackend())

    assert client.evaluations("crew-that-does-not-exist") == []
