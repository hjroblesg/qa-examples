"""Command-line front-end for the framework's engine.

Usage:
    python -m ctf --command run_container --image acme/mysql --tag 8.0
"""
import sys
import logging
import argparse

from ctf.engine.docker import Docker


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
    return parser


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
        result = fn(args.image_names[0], tag)
        log.info(result)
    except Exception as e:  # noqa: BLE001 - top-level CLI guard
        log.exception(f"An error occurred while executing command: {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
