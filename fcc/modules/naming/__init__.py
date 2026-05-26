"""Naming cleanup/subtitles module metadata and API/service entrypoints."""

from fcc.modules import Module, register

module = Module(name="naming", display_name="Naming", description="Directory cleanup module")
register(module)
