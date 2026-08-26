"""Unit tests for the container-validation core (``ctf.engine.docker.Docker``).

These tests exercise the validator's *logic* — the shell commands it builds and
the branches it takes — with the subprocess boundary mocked out (see
``conftest.docker``). No Docker daemon is required.

Techniques demonstrated, mapped to tests:
  * Mock injection / isolation ............ every test (``docker`` fixture)
  * Command-string assertions ............. Test*Command classes
  * ``@pytest.mark.parametrize`` .......... parametrized default-tag + rc cases
  * ``pytest.raises`` ..................... test_image_ref.py (empty reference)
  * ``side_effect`` sequencing ............ multi-call flows (pull/run)
  * Boundary / edge cases ................. tests marked ``edge`` + regression
  * Regression pinning .................... tests marked ``regression`` pin a
                                            defect these tests uncovered
"""
import pytest

from ctf.engine import config

pytestmark = [pytest.mark.unit, pytest.mark.docker_logic]


# --------------------------------------------------------------------------- #
# query_container                                                             #
# --------------------------------------------------------------------------- #
class TestQueryContainer:
    def test_builds_expected_image_grep_command(self, docker, sent_commands):
        docker.exec_utils.execute_commands.return_value = ("mysql:8.0", 0)

        result = docker.query_container("mysql", "8.0")

        assert result == "mysql:8.0"                       # pass-through of stdout
        assert sent_commands() == [
            'docker images --format "{{.Repository}}:{{.Tag}}" | grep mysql:8.0'
        ]
        docker.exec_utils.execute_commands.assert_called_once()

    def test_tag_defaults_to_latest(self, docker, sent_commands):
        docker.query_container("mysql")
        assert sent_commands() == [
            'docker images --format "{{.Repository}}:{{.Tag}}" | grep mysql:latest'
        ]

    @pytest.mark.parametrize(
        "name, tag, expected_suffix",
        [
            ("mysql", "8.0", "grep mysql:8.0"),
            ("redis", "7", "grep redis:7"),
            ("ghcr.io/acme/api", "v1.2", "grep ghcr.io/acme/api:v1.2"),
        ],
    )
    def test_parametrized_names_and_tags(self, docker, sent_commands, name, tag, expected_suffix):
        docker.query_container(name, tag)
        assert sent_commands()[0].endswith(expected_suffix)


# --------------------------------------------------------------------------- #
# ps_container                                                                 #
# --------------------------------------------------------------------------- #
class TestPsContainer:
    def test_builds_ps_grep_awk_command(self, docker, sent_commands):
        docker.exec_utils.execute_commands.return_value = ("Up 3 minutes", 0)

        result = docker.ps_container("mysql", "8.0")

        assert result == "Up 3 minutes"
        assert sent_commands() == [
            "docker ps -a |grep mysql-8.0 | awk '{print $10}'"
        ]

    def test_tag_defaults_to_latest(self, docker, sent_commands):
        docker.ps_container("mysql")
        assert "grep mysql-latest" in sent_commands()[0]


# --------------------------------------------------------------------------- #
# pull_container                                                               #
# --------------------------------------------------------------------------- #
class TestPullContainer:
    def test_short_circuits_when_image_already_present(self, docker, sent_commands):
        # query_container reports the image already exists locally...
        docker.exec_utils.execute_commands.return_value = ("mysql:8.0", 0)

        message = docker.pull_container("mysql", "8.0")

        assert message == "Container mysql:8.0 already pulled"
        # ...so only the query ran; no `docker pull` was issued.
        assert sent_commands() == [
            'docker images --format "{{.Repository}}:{{.Tag}}" | grep mysql:8.0'
        ]

    def test_pulls_when_image_absent(self, docker, sent_commands):
        # 1st call = query (image absent -> ""), 2nd call = the pull itself.
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]

        message = docker.pull_container("mysql", "8.0")

        assert message == "Container mysql:8.0 successfully pulled"
        # The reference is used verbatim — the official image is `mysql:8.0`,
        # NOT the fabricated `mysql/mysql:8.0`.
        assert sent_commands()[-1] == "docker pull mysql:8.0"

    def test_pulls_namespaced_image_verbatim(self, docker, sent_commands):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]

        message = docker.pull_container("bitnami/mysql", "8.0")

        assert message == "Container bitnami/mysql:8.0 successfully pulled"
        assert sent_commands()[-1] == "docker pull bitnami/mysql:8.0"

    def test_tag_embedded_in_image_reference_wins(self, docker, sent_commands):
        # No explicit tag arg -> the tag inside the reference is used.
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]

        message = docker.pull_container("mysql:5.7")

        assert message == "Container mysql:5.7 successfully pulled"
        assert sent_commands()[-1] == "docker pull mysql:5.7"

    def test_reports_error_on_nonzero_pull(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("no such host", 1)]

        message = docker.pull_container("mysql", "8.0")

        assert message == "Error attempting pull command: no such host"

    @pytest.mark.edge
    def test_unexpected_return_code_on_pull(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("weird", 137)]
        assert docker.pull_container("mysql", "8.0") == "Something wrong happened"

    @pytest.mark.regression
    def test_tag_mismatch_triggers_pull_not_unbound_message(self, docker, sent_commands):
        """Bug #1: image name present but a *different* tag installed.

        The original code hit ``elif name in result`` then fell through the
        inner ``if tag in result`` with no ``else``, leaving ``message``
        unbound -> UnboundLocalError. Correct behaviour: the requested tag is
        absent, so we pull it.
        """
        # query returns a different tag (5.7) than requested (8.0)
        docker.exec_utils.execute_commands.side_effect = [("mysql:5.7", 0), ("", 0)]

        message = docker.pull_container("mysql", "8.0")

        assert message == "Container mysql:8.0 successfully pulled"
        assert sent_commands()[-1] == "docker pull mysql:8.0"


# --------------------------------------------------------------------------- #
# run_container                                                                #
# --------------------------------------------------------------------------- #
class TestRunContainer:
    def test_runs_with_docker_options_when_not_yet_created(self, docker, sent_commands):
        from ctf.engine import config
        # ps -> "" (not running), then run -> success
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]

        message = docker.run_container("acme/mysql", "8.0")

        assert message == "Container is running under name: mysql-8.0"
        run_cmd = sent_commands()[-1]
        assert run_cmd.startswith("docker run --name mysql-8.0 ")
        assert config.DOCKER_OPTNS in run_cmd
        assert run_cmd.endswith("acme/mysql:8.0")

    def test_reports_error_on_nonzero_run(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("port in use", 1)]
        message = docker.run_container("acme/mysql", "8.0")
        assert message == "Error attempting run command: port in use"

    def test_run_options_inject_env_and_ports(self, docker, sent_commands):
        """RunOptions lets the engine launch env-driven images like MySQL."""
        from ctf.engine.run_options import RunOptions
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]

        message = docker.run_container(
            "mysql", "8.0",
            RunOptions(
                env={"MYSQL_ROOT_PASSWORD": "secret", "MYSQL_DATABASE": "testdb"},
                ports={3306: 3306},
                options="-d",
            ),
        )

        assert message == "Container is running under name: mysql-8.0"
        assert sent_commands()[-1] == (
            "docker run --name mysql-8.0 -d -p 3306:3306 "
            "-e MYSQL_ROOT_PASSWORD=secret -e MYSQL_DATABASE=testdb mysql:8.0"
        )

    def test_default_run_still_uses_framework_options(self, docker, sent_commands):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]
        docker.run_container("acme/mysql", "8.0")
        run_cmd = sent_commands()[-1]
        assert config.DOCKER_OPTNS in run_cmd and run_cmd.endswith("acme/mysql:8.0")

    @pytest.mark.edge
    def test_unexpected_return_code_on_run(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("weird", 137)]
        assert docker.run_container("acme/mysql", "8.0") == "Something else happened"

    @pytest.mark.regression
    def test_already_created_returns_message(self, docker, sent_commands):
        """Bug #2: when ps reports the container exists, the original code only
        logged and returned an unbound ``message`` -> UnboundLocalError."""
        docker.exec_utils.execute_commands.return_value = ("Up 2 minutes", 0)

        message = docker.run_container("acme/mysql", "8.0")

        assert message == "Container mysql-8.0 already created"
        # short-circuited: only ps ran, no `docker run`
        assert all("docker run" not in c for c in sent_commands())

    @pytest.mark.regression
    def test_bare_official_image_runs_without_registry(self, docker, sent_commands):
        """Bug #3 (revised): the old code required a ``registry/name`` image and
        blew up on a bare official name like ``mysql``. With ImageRef parsing,
        ``mysql`` is a valid reference and runs as ``mysql:8.0`` under the
        container name ``mysql-8.0``."""
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]

        message = docker.run_container("mysql", "8.0")

        assert message == "Container is running under name: mysql-8.0"
        run_cmd = sent_commands()[-1]
        assert run_cmd.startswith("docker run --name mysql-8.0 ")
        assert run_cmd.endswith("mysql:8.0")


# --------------------------------------------------------------------------- #
# teardown_container                                                           #
# --------------------------------------------------------------------------- #
class TestTeardownContainer:
    def test_builds_stop_and_rm_command(self, docker, sent_commands):
        message = docker.teardown_container("mysql", "8.0")
        assert sent_commands() == ["docker stop mysql-8.0; docker rm mysql-8.0"]
        assert message == "Container successfully deleted: mysql-8.0"

    def test_reports_error_on_nonzero_teardown(self, docker):
        docker.exec_utils.execute_commands.return_value = ("No such container", 1)
        message = docker.teardown_container("mysql", "8.0")
        assert message == "Error attempting run command: No such container"

    @pytest.mark.edge
    @pytest.mark.regression
    def test_unexpected_return_code_still_returns_message(self, docker):
        """Bug #4: a return code other than 0/1 left ``message`` unbound."""
        docker.exec_utils.execute_commands.return_value = ("weird", 137)
        message = docker.teardown_container("mysql", "8.0")
        assert message == "Something else happened"


# --------------------------------------------------------------------------- #
# copy_file                                                                    #
# --------------------------------------------------------------------------- #
class TestCopyFile:
    def test_copy_into_container(self, docker, sent_commands):
        docker.copy_file("mysql", "8.0", dest="to container", path="/tmp/seed.sql")
        assert sent_commands() == ["docker cp /tmp/seed.sql mysql-8.0:/"]

    @pytest.mark.regression
    def test_copy_out_of_container_uses_workdir(self, docker, sent_commands):
        """Bug #5: the copy-out branch referenced ``self.workdir`` which was
        never initialised -> AttributeError. It is now set in __init__."""
        docker.workdir = "/work"
        docker.copy_file("mysql", "8.0", dest="from container", path="/var/log/x.log")
        assert sent_commands() == ["docker cp mysql-8.0:/var/log/x.log /work/logs"]


# --------------------------------------------------------------------------- #
# Cross-cutting: isolation guarantee                                          #
# --------------------------------------------------------------------------- #
class TestOutcomeFlag:
    """docker.ok reflects the success of the last lifecycle command; the CLI
    maps it to its exit code."""

    def test_pull_success_sets_ok_true(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]
        docker.pull_container("mysql", "8.0")
        assert docker.ok is True

    def test_pull_failure_sets_ok_false(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("no such host", 1)]
        docker.pull_container("mysql", "8.0")
        assert docker.ok is False

    def test_already_pulled_sets_ok_true(self, docker):
        docker.exec_utils.execute_commands.return_value = ("mysql:8.0", 0)
        docker.pull_container("mysql", "8.0")
        assert docker.ok is True

    def test_run_success_sets_ok_true(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("", 0)]
        docker.run_container("acme/mysql", "8.0")
        assert docker.ok is True

    def test_run_failure_sets_ok_false(self, docker):
        docker.exec_utils.execute_commands.side_effect = [("", 0), ("port in use", 1)]
        docker.run_container("acme/mysql", "8.0")
        assert docker.ok is False

    def test_teardown_failure_sets_ok_false(self, docker):
        docker.exec_utils.execute_commands.return_value = ("No such container", 1)
        docker.teardown_container("mysql", "8.0")
        assert docker.ok is False


@pytest.mark.unit
def test_no_real_subprocess_is_ever_spawned(docker):
    """Sanity check that the suite is hermetic: the execution seam is a mock,
    so nothing here can reach a real Docker daemon."""
    from unittest.mock import MagicMock
    assert isinstance(docker.exec_utils, MagicMock)
    docker.query_container("mysql", "8.0")
    docker.exec_utils.execute_commands.assert_called()
