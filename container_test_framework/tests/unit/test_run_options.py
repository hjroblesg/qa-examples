"""Unit tests for RunOptions and the CLI's run-option parsing."""
import pytest

from ctf.engine.run_options import RunOptions
from ctf.engine import config
from ctf.cli import build_run_options

pytestmark = pytest.mark.unit


class TestRunOptionsFlags:
    def test_default_is_the_framework_options(self):
        assert RunOptions().as_flags() == config.DOCKER_OPTNS

    def test_env_and_ports_with_custom_options(self):
        opts = RunOptions(
            env={"MYSQL_ROOT_PASSWORD": "secret", "MYSQL_DATABASE": "testdb"},
            ports={3306: 3306},
            options="-d",
        )
        assert opts.as_flags() == (
            "-d -p 3306:3306 "
            "-e MYSQL_ROOT_PASSWORD=secret -e MYSQL_DATABASE=testdb"
        )

    def test_empty_options_string_yields_only_env_ports(self):
        opts = RunOptions(env={"K": "v"}, ports={8080: 80}, options="")
        assert opts.as_flags() == "-p 8080:80 -e K=v"

    def test_env_value_with_spaces_is_shell_quoted(self):
        opts = RunOptions(env={"MSG": "hello world"}, options="")
        assert opts.as_flags() == "-e MSG='hello world'"

    def test_simple_env_value_is_not_quoted(self):
        opts = RunOptions(env={"PW": "ctf-secret"}, options="")
        assert opts.as_flags() == "-e PW=ctf-secret"


class TestBuildRunOptions:
    def test_parses_env_and_publish(self):
        opts = build_run_options(
            ["MYSQL_ROOT_PASSWORD=secret", "MYSQL_DATABASE=testdb"],
            ["3306:3306"],
            "-d",
        )
        assert opts.env == {"MYSQL_ROOT_PASSWORD": "secret", "MYSQL_DATABASE": "testdb"}
        assert opts.ports == {3306: 3306}
        assert opts.options == "-d"

    def test_env_value_may_contain_equals(self):
        opts = build_run_options(["TOKEN=a=b=c"], None, None)
        assert opts.env == {"TOKEN": "a=b=c"}

    def test_defaults_to_framework_options_when_run_opts_none(self):
        opts = build_run_options(None, None, None)
        assert opts.env == {} and opts.ports == {}
        assert opts.options == config.DOCKER_OPTNS

    @pytest.mark.edge
    def test_bad_env_without_equals_raises(self):
        with pytest.raises(ValueError, match="KEY=VALUE"):
            build_run_options(["NOEQUALS"], None, None)

    @pytest.mark.edge
    def test_bad_publish_without_colon_raises(self):
        with pytest.raises(ValueError, match="HOST:CONTAINER"):
            build_run_options(None, ["3306"], None)
