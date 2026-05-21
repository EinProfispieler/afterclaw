# Managed DDNS Service (Donor Token Model)

This service lets you keep Volcengine DNS credentials on your server while issuing per-user tokens for `xxx.afterclaw.xyz`.

## What It Provides

- Per-donor token issuance and revocation
- Token-bound FQDN (`alice.afterclaw.xyz`)
- DDNS update API (`/v1/ddns/update`)
- Ko-fi webhook API (`/v1/kofi/webhook`)
- Per-user setup page (`/u/<token>`)
- Basic rate limiting and update logs

Script: [scripts/managed_ddns_service.py](/Users/randy/afterclaw/scripts/managed_ddns_service.py)

## Data Model

SQLite database (default: `data/managed_ddns.sqlite3`):

- `tokens`
- `update_logs`
- `webhook_events` (idempotency / dedup by `message_id`)

Each token stores:

- `donor_id`
- `fqdn`
- `enabled`
- `expires_at`
- `min_interval_sec`
- `last_update_at`

## Issue / Revoke Tokens

Issue token:

```bash
python3 scripts/managed_ddns_service.py issue \
  --donor-id user_1001 \
  --fqdn alice.afterclaw.xyz \
  --days 30 \
  --min-interval-sec 60
```

Revoke token:

```bash
python3 scripts/managed_ddns_service.py revoke --token <TOKEN>
```

List active tokens:

```bash
python3 scripts/managed_ddns_service.py list
```

## Run the Service

```bash
python3 scripts/managed_ddns_service.py serve \
  --host 0.0.0.0 \
  --port 8098 \
  --ak '<VOLCENGINE_ACCESS_KEY_ID>' \
  --sk '<VOLCENGINE_SECRET_ACCESS_KEY>' \
  --kofi-verification-token '95ddb5af-855f-47ed-88a9-45b799f5929b' \
  --external-base-url 'https://ddns.afterclaw.xyz' \
  --billing-days 30 \
  --grace-days 7 \
  --ttl 600
```

## Endpoints

- `GET /health`
- `GET /setup` (token input page)
- `GET /u/<token>` (user-specific setup page)
- `POST /v1/ddns/update`
  - query/body: `token`, `ipv4` (optional), `ipv6` (optional)
- `POST /v1/kofi/webhook`
  - validates `verification_token`
  - dedup by `message_id` / `kofi_transaction_id`
  - extends donor token expiry: `+billing_days + grace_days`

Expire scan (run daily via cron/systemd timer):

```bash
python3 scripts/managed_ddns_service.py expire-scan
```

## User Flow (Paid Donor)

1. You issue token + bind FQDN.
2. User opens `https://ddns.afterclaw.xyz/u/<token>`.
3. The page shows a ready-to-paste URL template for AfterClaw DDNS HTTP provider.
4. User saves config and DDNS updates begin.
5. If no renewal arrives, token enters expired state after 30d+7d and is disabled by `expire-scan`.

## Nginx Example (ddns.afterclaw.xyz)

```nginx
server {
    listen 443 ssl http2;
    server_name ddns.afterclaw.xyz;

    location / {
        proxy_pass http://127.0.0.1:8098;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Operational Notes

- Keep AK/SK only on server side.
- Back up SQLite file.
- Put this process behind systemd and restart policy.
- Keep interval limits (`min_interval_sec`) to control abuse.
- Use donor email as `donor_id` when issuing tokens, so webhook renewals can match records.
