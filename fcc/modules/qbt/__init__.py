"""qBittorrent module metadata and API dispatch entrypoints."""

from fcc.modules import Module, register

module = Module(name="qbt", display_name="BitTorrent", description="qBittorrent discover/fix/optimize module")
register(module)
