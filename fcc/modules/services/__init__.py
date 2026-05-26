"""Services control module metadata and API dispatch entrypoints."""

from fcc.modules import Module, register

module = Module(name="services", display_name="Services", description="Service control module")
register(module)
