"""Unit tests for the execution seam (``utils.execute_utils.Utils``).

Here we mock one layer lower — ``subprocess.Popen`` itself — to prove the
wrapper decodes stdout and surfaces the process return code without ever
launching a real shell. Demonstrates monkeypatching a module-level dependency.
"""
import types
from unittest.mock import MagicMock

import pytest

from ctf.engine.executor import CommandExecutor

pytestmark = pytest.mark.unit


@pytest.fixture
def fake_popen(monkeypatch):
    """Replace subprocess.Popen inside execute_utils with a factory we control.

    Returns a helper to configure the fake process' stdout bytes and rc.
    Also pins sys.stdin.encoding (the code decodes with it) so the test is
    stable regardless of how the runner captures stdin.
    """
    monkeypatch.setattr(
        "ctf.engine.executor.sys.stdin",
        types.SimpleNamespace(encoding="utf-8"),
        raising=False,
    )

    proc = MagicMock(name="Popen()")

    def configure(stdout=b"", returncode=0):
        proc.communicate.return_value = (stdout, None)  # stderr merged via STDOUT
        proc.returncode = returncode
        return proc

    factory = MagicMock(name="Popen", return_value=proc)
    monkeypatch.setattr("ctf.engine.executor.subprocess.Popen", factory)
    configure()  # sensible default
    factory.configure = configure
    return factory


def test_returns_decoded_stdout_and_returncode(fake_popen):
    fake_popen.configure(stdout=b"mysql:8.0\n", returncode=0)

    out, rc = CommandExecutor().execute_commands(["docker images"])

    assert out == "mysql:8.0\n"
    assert rc == 0


def test_passes_command_to_bash_dash_c(fake_popen):
    CommandExecutor().execute_commands(["echo hi"])

    args, kwargs = fake_popen.call_args
    assert args[0] == ["/bin/bash", "-c", "echo hi"]
    assert kwargs["shell"] is False


def test_surfaces_nonzero_return_code(fake_popen):
    fake_popen.configure(stdout=b"boom", returncode=1)

    out, rc = CommandExecutor().execute_commands(["false"])

    assert (out, rc) == ("boom", 1)
