"""Docker module metadata plus API and service split entrypoints."""

from fcc.modules import Module, register

module = Module(
    name="docker",
    display_name="Docker",
    description="Docker inventory, logs, and safe start/stop/restart controls",
)
register(module)
