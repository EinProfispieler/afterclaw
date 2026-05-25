"""Docker module metadata.

The operational endpoints live in the main HTTP handler for now because they
reuse the existing LAN guard, JSON helpers, and service-control conventions.
"""

from fcc.modules import Module, register

module = Module(
    name="docker",
    display_name="Docker",
    description="Docker inventory, logs, and safe start/stop/restart controls",
)
register(module)
