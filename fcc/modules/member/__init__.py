"""Member module metadata and API dispatch entrypoints."""

from fcc.modules import Module, register

module = Module(name="member", display_name="Member", description="Member auth and profile module")
register(module)
