"""Shell execution seam.

The single point where the framework touches the outside world. Everything
above it (the Docker wrapper, the validators) is unit-tested by mocking this
class, so the rest of the framework stays fully deterministic.
"""
import sys
import subprocess
import logging

log = logging.getLogger("ctf.executor")


class CommandExecutor:
    """Run shell commands and return ``(decoded_stdout, return_code)``."""

    def execute_commands(self, commands):
        for command in commands:
            log.info(f"Execute command: {command}")
            process = subprocess.Popen(
                ["/bin/bash", "-c", command],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
            )
            out, _ = process.communicate()
            self.rc = process.returncode
            decoded = out.decode(sys.stdin.encoding or "utf-8", errors="ignore")
            log.info(decoded)
        return decoded, self.rc

    def execute_workload(self, container_name, container_tag, workload, term_mode="-t"):
        """Run one or more commands *inside* a running container via docker exec."""
        for command in workload:
            exec_options = f"{term_mode} {container_name}-{container_tag} bash -c {command}"
            docker_exec = [f"docker exec {exec_options}"]
            result, self.rc = self.execute_commands(docker_exec)
        return [result, self.rc]
