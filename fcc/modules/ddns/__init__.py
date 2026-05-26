"""DDNS module metadata and API dispatch entrypoints."""

from fcc.modules import Module, register

module = Module(name="ddns", display_name="DDNS", description="DDNS updater module")
register(module)
