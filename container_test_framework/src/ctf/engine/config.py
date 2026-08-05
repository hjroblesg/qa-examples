"""Engine configuration constants."""

# Default options passed to `docker run`. Tuned for privileged workload
# containers (device access, host networking). Adjust per target as needed.
DOCKER_OPTNS = (
    "-ti -d --privileged"
    " -e PYTHONUNBUFFERED=1 --network=host"
    " --security-opt label:disable"
    " --pid=host --cap-add=SYS_ADMIN --cap-add=SYS_PTRACE"
)
