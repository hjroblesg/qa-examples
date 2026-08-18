"""Unit tests for ``ctf.validators.api.APIValidator``.

The HTTP client is injected as a mock ``session_factory``, so these tests run
with **no server and without `requests` installed**. Each check is verified on
three fronts: the URL/params requested, how the response is interpreted, and
that failures become a failed ``ValidationResult`` rather than an exception.
"""
from unittest.mock import MagicMock

import pytest

from ctf.validators.api import APIConfig, APIValidator
from ctf.validators.base import ValidationResult

pytestmark = [pytest.mark.unit, pytest.mark.api]


def _response(status=200, json_body=None):
    resp = MagicMock(name="response")
    resp.status_code = status
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


@pytest.fixture
def session():
    return MagicMock(name="session")


@pytest.fixture
def validator(session):
    v = APIValidator(
        image="mccutchen/go-httpbin",
        config=APIConfig(base_url="http://127.0.0.1:8080"),
        session_factory=lambda: session,
    )
    return v, session


# --------------------------------------------------------------------------- #
# session management                                                          #
# --------------------------------------------------------------------------- #
class TestSession:
    def test_uses_injected_factory_and_memoizes(self):
        sess = MagicMock()
        factory = MagicMock(return_value=sess)
        v = APIValidator(session_factory=factory)
        assert v.session() is sess
        assert v.session() is sess
        factory.assert_called_once()

    def test_close_closes_and_clears(self, validator):
        v, sess = validator
        v.session()
        v.close()
        sess.close.assert_called_once()
        assert v._session is None
        v.close()  # idempotent

    def test_default_factory_lazily_imports_requests(self, monkeypatch):
        import sys
        fake_session = MagicMock(name="requests.Session()")
        fake_requests = MagicMock()
        fake_requests.Session.return_value = fake_session
        monkeypatch.setitem(sys.modules, "requests", fake_requests)

        v = APIValidator()
        assert v.session() is fake_session
        fake_requests.Session.assert_called_once()


# --------------------------------------------------------------------------- #
# health                                                                       #
# --------------------------------------------------------------------------- #
class TestHealth:
    def test_passes_on_expected_status(self, validator):
        v, sess = validator
        sess.get.return_value = _response(200)

        result = v.check_health()

        assert isinstance(result, ValidationResult)
        assert result.name == "health" and result.passed is True
        # URL is base_url + health_path, with a timeout
        sess.get.assert_called_once_with("http://127.0.0.1:8080/", timeout=v.config.timeout)

    def test_fails_on_wrong_status(self, validator):
        v, sess = validator
        sess.get.return_value = _response(503)
        result = v.check_health()
        assert result.passed is False
        assert "got 503" in result.detail

    def test_fails_gracefully_on_connection_error(self):
        boom = MagicMock()
        boom.get.side_effect = OSError("connection refused")
        v = APIValidator(session_factory=lambda: boom)
        result = v.check_health()
        assert result.passed is False
        assert "request failed" in result.detail


# --------------------------------------------------------------------------- #
# status-code endpoints                                                       #
# --------------------------------------------------------------------------- #
class TestEndpoints:
    def test_passes_when_status_matches(self, validator):
        v, sess = validator
        v.expected_endpoints = {"/status/404": 404}
        sess.get.return_value = _response(404)

        results = v.check_endpoints()

        assert results[0].name == "status:/status/404" and results[0].passed is True
        sess.get.assert_called_once_with("http://127.0.0.1:8080/status/404", timeout=v.config.timeout)

    def test_fails_when_status_mismatches(self, validator):
        v, sess = validator
        v.expected_endpoints = {"/status/500": 500}
        sess.get.return_value = _response(200)
        results = v.check_endpoints()
        assert results[0].passed is False
        assert "expected 500, got 200" in results[0].detail

    def test_empty_endpoints_yields_no_results(self, validator):
        v, _ = validator
        assert v.check_endpoints() == []

    def test_fails_gracefully_on_request_error(self, validator):
        v, sess = validator
        v.expected_endpoints = {"/get": 200}
        sess.get.side_effect = OSError("connection reset")
        results = v.check_endpoints()
        assert results[0].passed is False
        assert "connection reset" in results[0].detail


# --------------------------------------------------------------------------- #
# contract                                                                     #
# --------------------------------------------------------------------------- #
class TestContracts:
    def test_passes_when_all_keys_present(self, validator):
        v, sess = validator
        v.expected_contracts = {"/get": ["url", "headers"]}
        sess.get.return_value = _response(200, {"url": "...", "headers": {}, "args": {}})

        results = v.check_contracts()

        assert results[0].name == "contract:/get" and results[0].passed is True

    def test_fails_and_lists_missing_keys(self, validator):
        v, sess = validator
        v.expected_contracts = {"/get": ["url", "headers", "origin"]}
        sess.get.return_value = _response(200, {"url": "...", "headers": {}})
        results = v.check_contracts()
        assert results[0].passed is False
        assert "origin" in results[0].detail

    def test_fails_gracefully_on_non_json(self, validator):
        v, sess = validator
        v.expected_contracts = {"/get": ["url"]}
        resp = _response(200)
        resp.json.side_effect = ValueError("no JSON could be decoded")
        sess.get.return_value = resp
        results = v.check_contracts()
        assert results[0].passed is False
        assert "no JSON" in results[0].detail


# --------------------------------------------------------------------------- #
# checks() aggregation + URL building                                         #
# --------------------------------------------------------------------------- #
def test_checks_aggregates_all_dimensions(validator):
    v, sess = validator
    v.expected_endpoints = {"/status/404": 404}
    v.expected_contracts = {"/get": ["url"]}
    sess.get.return_value = _response(200, {"url": "..."})

    results = v.checks()

    names = [r.name for r in results]
    assert names == ["health", "status:/status/404", "contract:/get"]
    assert all(isinstance(r, ValidationResult) for r in results)


def test_setup_launches_via_engine_with_published_port():
    """setup() dogfoods the engine, publishing the API port via RunOptions."""
    from ctf.engine.run_options import RunOptions
    docker = MagicMock(name="docker")
    v = APIValidator(
        image="mccutchen/go-httpbin", tag="latest",
        config=APIConfig(host_port=8080, container_port=8080),
        docker=docker,
    )

    v.setup()

    docker.pull_container.assert_called_once_with("mccutchen/go-httpbin", "latest")
    docker.run_container.assert_called_once()
    args, _ = docker.run_container.call_args
    image, tag, options = args
    assert (image, tag) == ("mccutchen/go-httpbin", "latest")
    assert isinstance(options, RunOptions)
    assert options.ports == {8080: 8080}
    assert options.options == "-d"


def test_base_url_trailing_slash_is_normalized():
    sess = MagicMock()
    sess.get.return_value = _response(200)
    v = APIValidator(config=APIConfig(base_url="http://api:80/"), session_factory=lambda: sess)
    v.expected_endpoints = {"/get": 200}
    v.check_endpoints()
    # no double slash between base and path
    sess.get.assert_called_once_with("http://api:80/get", timeout=v.config.timeout)
