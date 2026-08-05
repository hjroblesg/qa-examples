"""Container-agnostic Docker CLI wrapper.

Builds and dispatches docker commands (query/pull/run/copy/teardown) through the
``CommandExecutor`` seam. Image references are parsed by ``ImageRef`` so the
engine uses the reference *verbatim* for pull/run (no fabricated registry) and
derives a stable container name for run/ps/rm. This makes official images
(``mysql``), namespaced images (``bitnami/mysql``) and private-registry
references all work.

Kept target-agnostic: MySQL, REST API and DL validators all reuse this class.
"""
import os
import logging

from ctf.engine import config
from ctf.engine.executor import CommandExecutor
from ctf.engine.image_ref import ImageRef

log = logging.getLogger("ctf.docker")


class Docker:
    def __init__(self) -> None:
        self.exec_utils = CommandExecutor()
        self.workdir = os.getcwd()

    def query_container(self, image, container_tag="latest"):
        """Return the local `docker images` line matching this reference, if any."""
        ref = ImageRef.parse(image, container_tag)
        command = [
            f"docker images --format \"{{{{.Repository}}}}:{{{{.Tag}}}}\""
            f" | grep {ref.repository}:{ref.tag}"
        ]
        result, self.rc = self.exec_utils.execute_commands(command)
        return result

    def ps_container(self, image, container_tag="latest"):
        ref = ImageRef.parse(image, container_tag)
        awk_cmd = r"awk '{print $10}'"
        command = [f"docker ps -a |grep {ref.container_name} | {awk_cmd}"]
        result, self.rc = self.exec_utils.execute_commands(command)
        return result

    def pull_container(self, image, container_tag="latest"):
        ref = ImageRef.parse(image, container_tag)
        # Use the reference exactly as given — no fabricated `registry/name`.
        command = [f"docker pull {ref.reference}"]
        result = self.query_container(image, container_tag).strip()
        # Short-circuit only when this exact repository AND tag are already local.
        if ref.repository in result and ref.tag in result:
            message = f"Container {ref.reference} already pulled"
            log.info(message)
            return message
        output, rc = self.exec_utils.execute_commands(command)
        if rc == 0:
            message = f"Container {ref.reference} successfully pulled"
        elif rc == 1:
            message = f"Error attempting pull command: {output}"
        else:
            message = f"Something wrong happened"
        log.info(message)
        return message

    def run_container(self, image, container_tag="latest"):
        ref = ImageRef.parse(image, container_tag)
        result = self.ps_container(image, container_tag)
        if result:
            message = f"Container {ref.container_name} already created"
            log.info(message)
            return message
        docker_options = config.DOCKER_OPTNS
        command = [
            f"docker run --name {ref.container_name} {docker_options} {ref.reference}"
        ]
        output, rc = self.exec_utils.execute_commands(command)
        if rc == 0:
            message = f"Container is running under name: {ref.container_name}"
        elif rc == 1:
            message = f"Error attempting run command: {output}"
        else:
            message = f"Something else happened"
        log.info(message)
        return message

    def copy_file(self, image, container_tag, dest, path=None):
        ref = ImageRef.parse(image, container_tag)
        if "to container" in dest:
            command = [f"docker cp {path} {ref.container_name}:/"]
        else:
            command = [f"docker cp {ref.container_name}:{path} {self.workdir}/logs"]
        self.exec_utils.execute_commands(command)

    def teardown_container(self, image, container_tag="latest"):
        ref = ImageRef.parse(image, container_tag)
        command = [f"docker stop {ref.container_name}; docker rm {ref.container_name}"]
        output, rc = self.exec_utils.execute_commands(command)
        if rc == 0:
            message = f"Container successfully deleted: {ref.container_name}"
        elif rc == 1:
            message = f"Error attempting run command: {output}"
        else:
            message = f"Something else happened"
        log.info(message)
        return message
