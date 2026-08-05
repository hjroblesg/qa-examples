"""Validator interface.

The contract every container target implements. The framework's engine handles
*lifecycle* (pull/run/teardown); a validator handles *correctness* — the
target-specific checks (MySQL schema/CRUD, API contract, DL thresholds).

Keeping this an ABC is what makes this a framework rather than a script: new
targets plug in without touching the engine or the test harness.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ctf.engine.docker import Docker


@dataclass
class ValidationResult:
    """Outcome of a single check."""
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ContainerValidator(ABC):
    """Base class for a target-specific container validator.

    Subclasses declare their ``image``/``tag`` and implement ``checks()``.
    ``validate()`` drives the standard lifecycle: pull -> run -> run checks ->
    (optionally) teardown, collecting a ``ValidationResult`` per check.
    """
    image: str
    tag: str = "latest"
    docker: Docker = field(default_factory=Docker)

    @abstractmethod
    def checks(self) -> list[ValidationResult]:
        """Return the target-specific validation results.

        Called once the container is up. Implementations connect to the running
        container and assert health/schema/contract/thresholds as appropriate.
        """
        raise NotImplementedError

    def setup(self) -> None:
        """Bring the target up. Override to add readiness/wait logic."""
        self.docker.pull_container(self.image, self.tag)
        self.docker.run_container(self.image, self.tag)

    def teardown(self) -> None:
        """Tear the target down."""
        self.docker.teardown_container(self.image, self.tag)

    def validate(self, teardown: bool = True) -> list[ValidationResult]:
        """Full lifecycle: setup -> checks -> teardown."""
        self.setup()
        try:
            return self.checks()
        finally:
            if teardown:
                self.teardown()
