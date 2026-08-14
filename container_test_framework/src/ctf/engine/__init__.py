"""Container-agnostic execution engine: shell executor + Docker CLI wrapper."""
from ctf.engine.docker import Docker
from ctf.engine.executor import CommandExecutor
from ctf.engine.image_ref import ImageRef
from ctf.engine.run_options import RunOptions

__all__ = ["Docker", "CommandExecutor", "ImageRef", "RunOptions"]
