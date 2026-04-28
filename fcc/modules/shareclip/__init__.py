"""ShareClip module placeholder and compatibility helpers."""

from __future__ import annotations

from fcc.modules import Module, register


module = Module(name="shareclip", display_name="ShareClip", description="LAN clipboard module")
register(module)


def shareclip_route_match(path: str, query_id_pub: bool = False) -> bool:
    # Transition phase: these routes are handled by legacy runtime.
    return False


def dispatch_shareclip(handler, parsed, method: str, send_body: bool = True) -> None:
    handler._error("ShareClip bridge is not enabled in modular server", status=404)
