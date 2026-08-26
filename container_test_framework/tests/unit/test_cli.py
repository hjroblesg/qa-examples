"""Unit tests for the CLI exit-code contract.

``ctf.cli.main`` returns 0 on success and 1 when the engine reports a failed
lifecycle command (via ``Docker.ok``) — so CI and the Robot suites can detect a
failed pull/run/remove. The Docker engine is replaced with a fake so no
subprocess is spawned.
"""
import pytest

import ctf.cli as cli

pytestmark = pytest.mark.unit


class FakeDocker:
    """Stand-in for the engine: records calls and reports ok via a flag."""
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def run_container(self, image, tag, options=None):
        self.calls.append(("run", image, tag))
        return "ran" if self.ok else "Error attempting run command: boom"

    def pull_container(self, image, tag):
        self.calls.append(("pull", image, tag))
        return "pulled" if self.ok else "Error attempting pull command: boom"

    def query_container(self, image, tag):
        self.calls.append(("query", image, tag))
        return "mysql:8.0"

    def ps_container(self, image, tag):
        self.calls.append(("ps", image, tag))
        return ""

    def teardown_container(self, image, tag):
        self.calls.append(("rm", image, tag))
        return "deleted" if self.ok else "Error attempting run command: boom"


@pytest.fixture
def patch_docker(monkeypatch):
    def _install(ok=True):
        fake = FakeDocker(ok=ok)
        monkeypatch.setattr(cli, "Docker", lambda: fake)
        return fake
    return _install


def test_run_success_exits_zero(patch_docker):
    patch_docker(ok=True)
    rc = cli.main(["--command", "run_container", "--image", "mysql", "--tag", "8.0"])
    assert rc == 0


def test_run_failure_exits_one(patch_docker):
    fake = patch_docker(ok=False)
    rc = cli.main(["--command", "run_container", "--image", "mysql", "--tag", "8.0"])
    assert rc == 1
    assert fake.calls == [("run", "mysql", "8.0")]


def test_pull_failure_exits_one(patch_docker):
    patch_docker(ok=False)
    rc = cli.main(["--command", "pull_container", "--image", "mysql", "--tag", "8.0"])
    assert rc == 1


def test_informational_command_exits_zero(patch_docker):
    # query_container doesn't touch ok; a fresh engine defaults to ok=True.
    patch_docker(ok=True)
    rc = cli.main(["--command", "query_container", "--image", "mysql", "--tag", "8.0"])
    assert rc == 0


def test_run_passes_env_and_publish_through(patch_docker, monkeypatch):
    fake = patch_docker(ok=True)
    captured = {}
    orig = fake.run_container

    def spy(image, tag, options=None):
        captured["options"] = options
        return orig(image, tag, options)

    fake.run_container = spy
    rc = cli.main([
        "--command", "run_container", "--image", "mysql", "--tag", "8.0",
        "--run-opts=-d", "--publish", "3306:3306",
        "--env", "MYSQL_ROOT_PASSWORD=secret",
    ])
    assert rc == 0
    opts = captured["options"]
    assert opts.ports == {3306: 3306}
    assert opts.env == {"MYSQL_ROOT_PASSWORD": "secret"}
    assert opts.options == "-d"


def test_missing_required_args_errors(patch_docker):
    # --command and --image are required; argparse errors out (SystemExit).
    patch_docker()
    with pytest.raises(SystemExit):
        cli.main(["--image", "mysql"])
