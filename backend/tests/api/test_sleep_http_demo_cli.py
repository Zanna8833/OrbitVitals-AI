"""Sleep CLI and standard-library transport checks, with no network access in tests."""

import io
import json
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from scripts import demo_sleep_http as demo
from tests.api.test_sleep_http_demo import asgi_requester


def attach_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace only the network transport, retaining real routes and algorithms."""
    transport = asgi_requester(client)

    def request(
        method: str,
        url: str,
        payload: demo.JsonObject | None,
        **kwargs: Any,
    ) -> tuple[int, demo.JsonObject]:
        return transport(method, url, payload)

    monkeypatch.setattr(demo, "http_request", request)


@pytest.mark.parametrize("full", [False, True])
def test_cli_outputs_actual_responses_and_validates_schemas(
    full: bool,
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    attach_client(api_client, monkeypatch)
    args = ["--validate"] + (["--full"] if full else [])
    assert demo.main(args) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert output.err == ""
    assert report["all_checks_passed"]
    assert report["data_kind"] == "simulated"
    assert report["schema_validation"] == "passed"
    if full:
        assert report["validated_response_payloads"] == 104
        assert len(report["http_exchanges"]) == 23
        assert (
            report["cases"][0]["evaluation_response"]
            == report["cases"][0]["stored_evaluation_response"]
        )
        methods = {item["method"] for item in report["http_exchanges"]}
        assert methods == {"GET", "POST"}
    else:
        assert "http_exchanges" not in report
        assert report["cases"][0]["duration_median_minutes"] == 430
        assert all(case["stored_evaluation_matches"] for case in report["cases"])


def test_help_does_not_contact_a_server(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        demo.main(["--help"])
    assert error.value.code == 0
    assert "SIMULATED DATA" in capsys.readouterr().out


@pytest.mark.parametrize("namespace", ["", "a" * 33, "with spaces", "../other", "name/crew"])
def test_invalid_namespace_is_rejected_before_http(namespace: str) -> None:
    with pytest.raises(demo.DemoError, match="namespace"):
        demo.run_demo(namespace=namespace, requester=lambda *args: pytest.fail("Unexpected HTTP"))


def test_maximum_namespace_still_produces_valid_opaque_identifiers() -> None:
    for case in demo.build_cases("a" * 32):
        assert len(case["crew_member_id"]) <= 128
        assert all(
            len(item["measurement_id"]) <= 128 for item in case["measurement_batch"]["measurements"]
        )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com/api/v1",
        "ftp://localhost/api/v1",
        "http://127.0.0.1:8000",
        "http://name:secret@localhost/api/v1",
        "http://localhost/api/v1?token=x",
        "http://localhost/api/v1#fragment",
    ],
)
def test_demo_only_sends_to_an_explicit_local_api_base(base_url: str) -> None:
    with pytest.raises(demo.DemoError, match="local HTTP"):
        demo.run_demo(base_url, requester=lambda *args: pytest.fail("Unexpected HTTP"))


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_invalid_timeouts_are_rejected_before_http(timeout: float) -> None:
    with pytest.raises(demo.DemoError, match="timeout"):
        demo.run_demo(timeout=timeout, requester=lambda *args: pytest.fail("Unexpected HTTP"))


def test_real_http_status_errors_are_reported_without_fabricated_success() -> None:
    with pytest.raises(demo.DemoError, match="received 404"):
        demo.run_demo(requester=lambda *args: (404, {"detail": "Not Found"}))


def test_wrong_service_or_metric_catalog_stops_before_ingestion(api_client: TestClient) -> None:
    transport = asgi_requester(api_client)
    calls = []

    def invalid_catalog(
        method: str, url: str, payload: demo.JsonObject | None
    ) -> tuple[int, demo.JsonObject]:
        calls.append(method)
        status, body = transport(method, url, payload)
        if url.endswith("/metrics"):
            next(item for item in body["items"] if item["metric"] == "sleep_duration")["unit"] = (
                "hours"
            )
        return status, body

    with pytest.raises(demo.DemoError, match="canonical sleep metrics"):
        demo.run_demo(requester=invalid_catalog)
    assert calls == ["GET", "GET"]
    with pytest.raises(demo.DemoError, match="identify itself"):
        demo.run_demo(requester=lambda *args: (200, {"status": "ok", "service": "another-api"}))


def test_id_match_without_content_match_returns_failure_exit(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    transport = asgi_requester(api_client)

    def changed_get(
        method: str,
        url: str,
        payload: demo.JsonObject | None,
        **kwargs: Any,
    ) -> tuple[int, demo.JsonObject]:
        status, body = transport(method, url, payload)
        if method == "GET" and "/evaluations?" in url and body["items"]:
            body["items"][0]["summary"] += " Test mismatch."
        return status, body

    monkeypatch.setattr(demo, "http_request", changed_get)
    assert demo.main([]) == 1
    report = json.loads(capsys.readouterr().out)
    assert not report["all_checks_passed"]
    assert all(not case["stored_evaluation_matches"] for case in report["cases"])


def test_unavailable_server_has_a_clear_diagnostic_and_error_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable(*args: Any, **kwargs: Any) -> tuple[int, demo.JsonObject]:
        raise demo.DemoError("The existing local server is unavailable")

    monkeypatch.setattr(demo, "http_request", unavailable)
    assert demo.main([]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Sleep HTTP demonstration failed" in output.err


def test_schema_validation_uses_actual_response_bodies(api_client: TestClient) -> None:
    report = demo.run_demo(requester=asgi_requester(api_client))
    exchange = next(
        item
        for item in report["http_exchanges"]
        if item["method"] == "POST" and item["path"] == "/measurements"
    )
    exchange["response"]["items"][0]["value"] = "not a number"
    with pytest.raises(demo.DemoError, match="Schema mismatch"):
        demo.validate_responses(report)


def test_transport_uses_json_and_preserves_http_error_response_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []

    class Opener:
        def open(self, request: Any, *, timeout: float) -> Any:
            captured.append((request, timeout))
            raise HTTPError(
                request.full_url,
                422,
                "Invalid request",
                {},
                io.BytesIO(b'{"detail": [{"msg": "test validation error"}]}'),
            )

    monkeypatch.setattr(demo, "build_opener", lambda *args: Opener())
    status, payload = demo.http_request(
        "POST", demo.DEFAULT_BASE_URL + "/measurements", {"measurements": []}
    )
    assert status == 422
    assert payload["detail"][0]["msg"] == "test validation error"
    request, timeout = captured[0]
    assert request.method == "POST"
    assert json.loads(request.data) == {"measurements": []}
    assert timeout == 10
    assert request.get_header("Content-type") == "application/json"


@pytest.mark.parametrize("body", [b"not json", b"[]"])
def test_non_json_or_non_object_http_responses_fail_clearly(
    body: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Response(io.BytesIO):
        code = 200

    class Opener:
        def open(self, *args: Any, **kwargs: Any) -> Response:
            return Response(body)

    monkeypatch.setattr(demo, "build_opener", lambda *args: Opener())
    with pytest.raises(demo.DemoError, match="Request failed|JSON object"):
        demo.http_request("GET", demo.DEFAULT_BASE_URL + "/health", None)


def test_transport_connection_errors_are_wrapped_without_attempted_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Opener:
        def open(self, *args: Any, **kwargs: Any) -> Any:
            calls.append(True)
            raise URLError("Connection refused")

    monkeypatch.setattr(demo, "build_opener", lambda *args: Opener())
    with pytest.raises(demo.DemoError, match="Connection refused"):
        demo.http_request("GET", demo.DEFAULT_BASE_URL + "/health", None)
    assert len(calls) == 1


def test_bad_server_list_shape_and_missing_quality_fail_explicitly(api_client: TestClient) -> None:
    transport = asgi_requester(api_client)

    def no_quality(
        method: str, url: str, payload: demo.JsonObject | None
    ) -> tuple[int, demo.JsonObject]:
        status, body = transport(method, url, payload)
        if method == "POST" and url.endswith("/measurements"):
            body["items"][0]["data_quality"] = None
        return status, body

    with pytest.raises(demo.DemoError, match="engine assessment"):
        demo.run_demo(requester=no_quality)

    def invalid_list(
        method: str, url: str, payload: demo.JsonObject | None
    ) -> tuple[int, demo.JsonObject]:
        if url.endswith("/metrics"):
            return 200, {"records": []}
        return transport(method, url, payload)

    with pytest.raises(demo.DemoError, match="items envelope"):
        demo.run_demo(requester=invalid_list)


def test_json_encoder_rejects_non_finite_output() -> None:
    with pytest.raises(ValueError):
        demo.encode({"value": float("nan")})
