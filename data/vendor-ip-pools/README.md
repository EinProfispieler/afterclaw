# Vendor IP Pools

This directory is used by AfterClaw HTTP source sync:

- `github:Einprofispieler/afterclaw/data/vendor-ip-pools`

## Rules

- File names should include vendor keywords: `baidu`, `guangya`, `aliyun`.
- One IP/CIDR per line.
- Supports comments starting with `#` or `//`.
- Optional mixed syntax is supported: `baidu: 112.80.248.0/21`.

## Suggested files

- `baidu.txt`
- `guangya.txt`
- `aliyun.txt`
