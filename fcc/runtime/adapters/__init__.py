"""Thin adapters around OS-level commands used by runtime APIs."""

from .service_adapter import (
    ServiceActionResult,
    execute_systemctl,
    execute_service_action,
    restart_service,
    self_restart_commands,
)
from .docker_adapter import DockerCommandResult, docker_available, execute_docker
from .process_adapter import CommandResult, choose_process_tool, execute_command, execute_process_tool

__all__ = [
    "ServiceActionResult",
    "execute_systemctl",
    "execute_service_action",
    "restart_service",
    "self_restart_commands",
    "DockerCommandResult",
    "docker_available",
    "execute_docker",
    "CommandResult",
    "choose_process_tool",
    "execute_command",
    "execute_process_tool",
]
