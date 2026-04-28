"""项目内置 DDNS：多文件拆分，可替代本机 ddns-go（含火山 TrafficRoute 等）。"""

from .config_store import apply_config_from_body, config_path, load_config, save_config
from .service import (
    do_update_once,
    merge_builtin_into_systemd_shape,
    service_action,
    start_worker,
    status_for_api,
)

__all__ = [
    "apply_config_from_body",
    "config_path",
    "load_config",
    "save_config",
    "do_update_once",
    "merge_builtin_into_systemd_shape",
    "service_action",
    "start_worker",
    "status_for_api",
]
