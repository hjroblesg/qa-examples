"""REST API container validator.

Validates a running HTTP API container along three axes:

* **health** — does the health endpoint return the expected status?
* **status codes** — do specific paths return the codes they should
  (including negative cases like 404 / 401)?
* **contract** — does a JSON response contain the expected top-level keys?

Same testability design as the MySQL validator: the HTTP client is *injected*.
``session_factory`` is a zero-arg callable returning a ``requests.Session``-like
object; it defaults to ``requests.Session()`` (imported lazily, so unit tests
that supply a mock don't need ``requests`` installed). Every check returns a
``ValidationResult`` and never raises.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ctf.validators.base import ContainerValidator, ValidationResult
from ctf.engine.run_options import RunOptions

log = logging.getLogger("ctf.validators.api")


@dataclass
class APIConfig:
    base_url: str = "http://127.0.0.1:8080"
    timeout: float = 10.0
    health_path: str = "/"
    expected_status: int = 200
    # host<-container port mapping used when the engine launches the container
    host_port: int = 8080
    container_port: int = 8080


@dataclass
class APIValidator(ContainerValidator):
    # mccutchen/go-httpbin: maintained, multi-arch httpbin; listens on :8080
    image: str = "mccutchen/go-httpbin"
    tag: str = "latest"

    config: APIConfig = field(default_factory=APIConfig)
    # path -> expected HTTP status code
    expected_endpoints: dict[str, int] = field(default_factory=dict)
    # path -> expected top-level JSON keys
    expected_contracts: dict[str, list[str]] = field(default_factory=dict)
    # Injectable HTTP session factory (defaults to requests.Session).
    session_factory: Optional[Callable[[], Any]] = None

    _session: Any = field(default=None, init=False, repr=False)

    # -- session management ------------------------------------------------ #
    def session(self) -> Any:
        if self._session is None:
            factory = self.session_factory or self._default_factory
            self._session = factory()
        return self._session

    def _default_factory(self) -> Any:
        import requests  # lazy: only needed for real (integration) runs
        return requests.Session()

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            finally:
                self._session = None

    def _get(self, path: str) -> Any:
        url = self.config.base_url.rstrip("/") + "/" + path.lstrip("/")
        return self.session().get(url, timeout=self.config.timeout)

    # -- individual checks ------------------------------------------------- #
    def check_health(self) -> ValidationResult:
        try:
            resp = self._get(self.config.health_path)
            ok = resp.status_code == self.config.expected_status
            detail = (
                f"{self.config.health_path} -> {resp.status_code}" if ok
                else f"expected {self.config.expected_status}, got {resp.status_code}"
            )
            return ValidationResult("health", ok, detail)
        except Exception as e:  # noqa: BLE001 - checks report, never raise
            return ValidationResult("health", False, f"request failed: {e}")

    def check_endpoints(self) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for path, expected_code in self.expected_endpoints.items():
            try:
                resp = self._get(path)
                ok = resp.status_code == expected_code
                detail = (
                    f"{path} -> {resp.status_code}" if ok
                    else f"{path}: expected {expected_code}, got {resp.status_code}"
                )
                results.append(ValidationResult(f"status:{path}", ok, detail))
            except Exception as e:  # noqa: BLE001
                results.append(ValidationResult(f"status:{path}", False, str(e)))
        return results

    def check_contracts(self) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for path, keys in self.expected_contracts.items():
            try:
                resp = self._get(path)
                body = resp.json()
                missing = [k for k in keys if k not in body]
                ok = not missing
                detail = "all expected keys present" if ok else f"missing keys: {missing}"
                results.append(ValidationResult(f"contract:{path}", ok, detail))
            except Exception as e:  # noqa: BLE001
                results.append(ValidationResult(f"contract:{path}", False, str(e)))
        return results

    # -- lifecycle override ------------------------------------------------ #
    def setup(self) -> None:
        """Bring the API up through the engine, publishing its port."""
        self.docker.pull_container(self.image, self.tag)
        options = RunOptions(
            ports={self.config.host_port: self.config.container_port},
            options="-d",
        )
        self.docker.run_container(self.image, self.tag, options)

    # -- ContainerValidator hook ------------------------------------------- #
    def checks(self) -> list[ValidationResult]:
        results: list[ValidationResult] = [self.check_health()]
        results.extend(self.check_endpoints())
        results.extend(self.check_contracts())
        return results
