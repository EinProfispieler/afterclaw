# ShareClip

Share clipboard text/images across LAN machines with per-ID isolation.

## Features

- Paste text/image on one machine and read on others via web.
- Keep history and delete specific records.
- Multi-user isolation by ID (`Randy`, `Alice`, etc.).
- Config page for default port/default ID.
- Dark, improved UI.

## Storage Model

- Default storage root: `./storage` (relative to `app.py`).
- Per ID:
  - `<storage_root>/<id>/state.json` (latest + history metadata in one file)
  - `<storage_root>/<id>/images/*` (image files)
- Optional override: `SHARECLIP_STORAGE_ROOT`

Notes:
- UI and APIs do not expose server-side directory paths.
- Legacy `/storage/<id>/latest.json` + `/storage/<id>/history.json` data is auto-migrated on read.

## API

- `GET /api/config`
- `POST /api/config`
- `GET /api/clip?id=<id>`
- `POST /api/clip` (form field `id`)
- `GET /api/history?id=<id>&limit=200`
- `DELETE /api/history/<record_id>?id=<id>`
- `GET /api/clip/raw?id=<id>`

## Run

Linux:

```bash
cd /home/<user>/shareclip
python3 -m pip install -r requirements.txt
python3 app.py
```

Windows:

```powershell
cd C:\shareclip
python -m pip install -r requirements.txt
python app.py
```

## Storage Setup Script (Recommended)

Use this before first run (or before switching storage root):

```bash
chmod +x ./scripts/setup_storage.sh
./scripts/setup_storage.sh --root /var/lib/shareclip --user <service-user> --group <service-group> --apply-systemd
```

What it does:

- Creates storage root
- Applies owner/group (`chown`)
- Applies permissions (`chmod`: dirs 750, files 640)
- Writes `<storage_root>/config.json`
- Optionally writes systemd override env `SHARECLIP_STORAGE_ROOT` and restarts service

## Author & License

- Author: [RandyPKU](mailto:mengke@pku.org.cn)
- License: Apache License 2.0
- Repository: https://github.com/EinProfispieler/shareclip
