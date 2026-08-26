"""Command-line front-end for the framework's engine.

Usage:
    python -m ctf --command run_container --image acme/mysql --tag 8.0
    python -m ctf --command run_container --image mysql --tag 8.0 \\
        --run-opts "-d" --publish 3306:3306 --env MYSQL_ROOT_PASSWORD=secret
"""
import sys
import logging
import argparse

from ctf.engine.docker import Docker
from ctf.engine.run_options import RunOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctf",
        description="container-test-framework: container validation engine",
    )
    parser.add_argument(
        "--image", dest="image_names", nargs="*",
        help="Image(s) to verify. Example: --image acme/mysql",
    )
    parser.add_argument(
        "--tag", dest="tag", nargs="*", default=["latest"],
        help="Image tag(s) to verify. Example: --tag 8.0",
    )
    parser.add_argument(
        "--test", dest="test_names", nargs="*",
        help='Tests from the suite to run. Form: "label1 label2 ... labelN"',
    )
    parser.add_argument(
        "--exclude", dest="exclude_names", nargs="*",
        help='Tests to exclude. Form: "label1 label2 ... labelN"',
    )
    parser.add_argument(
        "--command", dest="command",
        choices=["query_container", "pull_container", "ps_container",
                 "run_container", "rm_container"],
        help="Engine command to execute.",
    )
    parser.add_argument(
        "--env", dest="env_vars", nargs="*", metavar="KEY=VALUE",
        help="Environment variables for run_container. Example: "
             "--env MYSQL_ROOT_PASSWORD=secret MYSQL_DATABASE=testdb",
    )
    parser.add_argument(
        "--publish", dest="publish", nargs="*", metavar="HOST:CONTAINER",
        help="Port mappings for run_container. Example: --publish 3306:3306",
    )
    parser.add_argument(
        "--run-opts", dest="run_opts", default=None,
        help="Override the default `docker run` flags for run_container "
             "(e.g. \"-d\"). Defaults to the framework's privileged options.",
    )
    return parser


def build_run_options(env_list, publish_list, run_opts):
    """Turn CLI --env/--publish/--run-opts values into a RunOptions."""
    env = {}
    for item in env_list or []:
        if "=" not in item:
            raise ValueError(f"--env expects KEY=VALUE, got: {item!r}")
        key, value = item.split("=", 1)
        env[key] = value
    ports = {}
    for item in publish_list or []:
        if ":" not in item:
            raise ValueError(f"--publish expects HOST:CONTAINER, got: {item!r}")
        host, container = item.split(":", 1)
        ports[int(host)] = int(container)
    kwargs = {"env": env, "ports": ports}
    if run_opts is not None:
        kwargs["options"] = run_opts
    return RunOptions(**kwargs)


def setup_logging() -> logging.Logger:
    log = logging.getLogger("ctf")
    log.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s - %(name)s - %(levelname)s] - %(message)s")
    )
    log.addHandler(handler)
    return log


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not any(vars(args).values()):
        parser.print_help()
        return 1

    if not args.command or not args.image_names:
        parser.error("--command and --image are required to run a command")

    log = setup_logging()
    docker = Docker()
    commands = {
        "query_container": docker.query_container,
        "ps_container": docker.ps_container,
        "pull_container": docker.pull_container,
        "run_container": docker.run_container,
        "rm_container": docker.teardown_container,
    }

    fn = commands[args.command]
    tag = args.tag[0] if isinstance(args.tag, list) else args.tag
    log.info(f"Executing command: {args.command}")
    try:
        if args.command == "run_container":
            options = build_run_options(args.env_vars, args.publish, args.run_opts)
            result = docker.run_container(args.image_names[0], tag, options)
        else:
            result = fn(args.image_names[0], tag)
        log.info(result)
    except Exception as e:  # noqa: BLE001 - top-level CLI guard
        log.exception(f"An error occurred while executing command: {e}")
        return 1
    # Lifecycle commands report success via docker.ok; a failed pull/run/remove
    # becomes a non-zero exit so callers (CI, the Robot suites) can detect it.
    return 0 if docker.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
