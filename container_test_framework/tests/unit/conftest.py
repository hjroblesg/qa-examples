"""Shared fixtures for the unit layer.

Design goal (see PROJECT_BRIEF): unit-test the *validator's logic* in
isolation. The only thing that touches the outside world is
``Utils.execute_commands`` (the subprocess boundary). We replace that single
seam with a mock, so every test below runs deterministically with **no Docker
daemon, no network and no real container**.
"""
import pytest
from unittest.mock import MagicMock

from ctf.engine.docker import Docker


@pytest.fixture
def docker():
    """A ``Docker`` instance whose execution seam is mocked.

    ``exec_utils.execute_commands`` returns ``(stdout, return_code)`` in the
    real code, so the mock defaults to ``("", 0)`` (empty output, success).
    Individual tests override ``.return_value`` or ``.side_effect``.
    """
    d = Docker()
    d.exec_utils = MagicMock(name="exec_utils")
    d.exec_utils.execute_commands.return_value = ("", 0)
    return d


@pytest.fixture
def sent_commands(docker):
    """Return the list of command strings passed to execute_commands so far.

    execute_commands is always called as ``execute_commands([cmd])``; this
    flattens every recorded call down to its single command string.
    """
    def _collect():
        return [call.args[0][0] for call in docker.exec_utils.execute_commands.call_args_list]
    return _collect
