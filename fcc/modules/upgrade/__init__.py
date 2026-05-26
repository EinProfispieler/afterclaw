"""Upgrade module metadata and API/service entrypoints."""

from fcc.modules import Module, register

module = Module(name="upgrade", display_name="Upgrade", description="Upgrade status and execution module")
register(module)
