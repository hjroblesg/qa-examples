"""Options for ``docker run``.

``run_container`` historically hard-coded a fixed set of privileged flags
(``config.DOCKER_OPTNS``) and had no way to pass environment variables or publish
ports — which is why a real MySQL (needs ``MYSQL_ROOT_PASSWORD`` and a published
3306) couldn't be launched through the engine. ``RunOptions`` closes that gap:
callers can add env vars, port mappings, and/or replace the default flag string.

Env values are passed through ``shlex.quote`` so a value with spaces or shell
metacharacters is escaped; simple values (e.g. ``ctf-secret``) are left as-is.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field

from ctf.engine import config


@dataclass
class RunOptions:
    #: environment variables -> ``-e KEY=VALUE``
    env: dict[str, str] = field(default_factory=dict)
    #: {host_port: container_port} -> ``-p HOST:CONTAINER``
    ports: dict[int, int] = field(default_factory=dict)
    #: raw ``docker run`` flags. Defaults to the framework's privileged set;
    #: override (e.g. ``"-d"``) when those flags don't suit the target.
    options: str = config.DOCKER_OPTNS

    def as_flags(self) -> str:
        """Render the options as a single ``docker run`` flag string."""
        parts: list[str] = []
        if self.options:
            parts.append(self.options)
        for host, container in self.ports.items():
            parts.append(f"-p {host}:{container}")
        for key, value in self.env.items():
            parts.append(f"-e {key}={shlex.quote(str(value))}")
        return " ".join(parts)
