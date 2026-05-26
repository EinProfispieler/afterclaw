"""Terminal module metadata and API/service entrypoints."""

from fcc.modules import Module, register

module = Module(name="terminal", display_name="Terminal", description="SSH terminal module")
register(module)
