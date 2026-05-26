# Backup Module

Directory-level backup orchestration integrated from TimeCapsule.

> Status (current release): disabled by default in `app.py` and not registered on
> the public route surface. This document describes the module internals only.

## Features

- **Intelligent File Classification**: Automatically categorizes files (code, AI, media, large files)
- **Incremental Backup**: Hash-based change detection to backup only modified files
- **Local Storage**: Backup to local disk with snapshot management
- **Web UI**: Modern management interface with real-time status

## Configuration

Default configuration is created at `data/backup_config.yaml`:

```yaml
version: "1.0"

sources:
  - path: ~/Projects
    include:
      - "**/*.py"
      - "**/*.js"
    exclude:
      - "**/node_modules/**"
      - "**/.venv/**"

targets:
  local:
    enabled: true
    path: ~/.afterclaw/backup

retention:
  daily: 7
  weekly: 4
  monthly: 12
```

## Public Surface Status

Current release intentionally disables Backup public routes/pages:

- `/backup`
- `/api/backup/*`

Reason: avoid exposing an incomplete/untested surface in production while keeping
the module implementation available for future re-enable.

## Development Usage (internal only)

If you are doing internal development on backup re-enable:

1. Keep config under `data/backup_config.yaml`
2. Re-enable route registration in app/runtime wiring explicitly
3. Add/refresh API tests and smoke checks before exposing routes again
4. Do not claim backup is public-ready until route surface + docs are both restored

## Architecture

- **Core**: File classification and incremental detection
- **Storage**: Pluggable storage backends (currently local disk)
- **Config**: YAML-based configuration management
- **Web**: REST API and UI integration

## File Categories

- **CODE**: Source code files (.py, .js, .ts, etc.)
- **AI**: AI-related files (.claude, .cursor, prompts, etc.)
- **MEDIA**: Images, videos, audio files
- **LARGE**: Files over 50MB
- **DOCUMENT**: Documents and PDFs
- **OTHER**: Everything else

## Exclusions

Automatically excludes common development artifacts:
- node_modules, .git, __pycache__
- venv, .venv, dist, build
- .idea, .vscode, .DS_Store
