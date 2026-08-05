"""Docker image-reference parsing.

A Docker reference looks like::

    [registry-host[:port]/][namespace/]repository[:tag][@digest]

The tricky parts are that the registry host may itself contain a ``:`` (port),
and that ``namespace``/``registry`` are optional. This parser splits a reference
into the pieces the engine actually needs:

* ``repository`` — exactly what you pass to ``docker pull`` (minus tag/digest),
  e.g. ``mysql``, ``bitnami/mysql``, ``reg.io:5000/team/app``.
* ``tag`` — the resolved tag (explicit tag wins over the CLI default).
* ``reference`` — ``repository:tag`` (or ``repository@digest``), the full
  pullable/runnable string.
* ``name`` / ``container_name`` — a short, stable name derived from the last
  path segment, used for ``docker run --name`` / ``ps`` / ``rm``.

Examples::

    mysql                              -> repo=mysql              name=mysql tag=latest
    mysql:8.0                          -> repo=mysql              name=mysql tag=8.0
    bitnami/mysql:8.0                  -> repo=bitnami/mysql      name=mysql tag=8.0
    reg.io:5000/team/app:1.2           -> repo=reg.io:5000/team/app  name=app  tag=1.2
    mysql@sha256:abc...                -> repo=mysql              name=mysql tag=latest digest=sha256:abc...
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ImageRef:
    repository: str
    tag: str = "latest"
    digest: Optional[str] = None

    @classmethod
    def parse(cls, image: str, default_tag: str = "latest") -> "ImageRef":
        """Parse a Docker image reference.

        A tag (``:tag``) is only recognised in the final path segment, so a
        registry port such as ``reg.io:5000/app`` is not mistaken for a tag. An
        explicit tag in ``image`` takes precedence over ``default_tag``.
        """
        if image is None or not image.strip():
            raise ValueError("image reference must not be empty")
        image = image.strip()

        # Peel off an optional @digest first.
        digest: Optional[str] = None
        if "@" in image:
            image, digest = image.split("@", 1)

        # A tag colon can only live in the segment after the last '/'.
        last_slash = image.rfind("/")
        last_segment = image[last_slash + 1:]
        if ":" in last_segment:
            name_part, tag = last_segment.rsplit(":", 1)
            prefix = image[: last_slash + 1] if last_slash >= 0 else ""
            repository = prefix + name_part
        else:
            repository = image
            tag = default_tag

        if not repository:
            raise ValueError(f"could not parse repository from image: {image!r}")

        return cls(repository=repository, tag=tag, digest=digest)

    @property
    def name(self) -> str:
        """Short name: the last path segment of the repository (used for --name)."""
        return self.repository.rsplit("/", 1)[-1]

    @property
    def reference(self) -> str:
        """Full pullable/runnable reference: repo@digest if pinned, else repo:tag."""
        if self.digest:
            return f"{self.repository}@{self.digest}"
        return f"{self.repository}:{self.tag}"

    @property
    def container_name(self) -> str:
        """Stable container name for run/ps/rm: ``<name>-<tag>``."""
        return f"{self.name}-{self.tag}"
