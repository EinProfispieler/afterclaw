"""DDNS 模块常量与默认配置。"""

CONFIG_FILE_NAME = "ddns_config.json"
IP_FAIL_BACKOFF = (0, 2, 5, 15, 60, 300)
VOLC_TR_VERSION = "2018-08-01"
VOLC_TR_SERVICE = "DNS"
VOLC_TR_REGION = "cn-north-1"
VOLC_TR_HOST = "open.volcengineapi.com"

DEFAULT_V4_URLS = (
    "https://ipv4.icanhazip.com",
    "https://ipv4.ip.sb",
    "https://checkip.amazonaws.com",
    "https://ip.3322.net",
    "https://myip.ipip.net",
)

DEFAULT_V6_URLS = (
    "https://v6.ident.me",
    "https://6.ipw.cn",
    "https://speed.neu6.edu.cn/getIP.php",
)
