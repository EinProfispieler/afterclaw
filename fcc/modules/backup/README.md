# Backup Module

Directory-level backup orchestration integrated from TimeCapsule.

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

## API Endpoints

- `GET /backup` - Backup management page
- `GET /api/backup/status` - Get backup status and statistics
- `POST /api/backup/run` - Execute backup now
- `GET /api/backup/list` - List all snapshots

## Usage

1. Start AfterClaw server:
   ```bash
   python3 app.py
   ```

2. Access backup page:
   ```
   http://localhost:1288/backup
   ```

3. Configure backup sources in `data/backup_config.yaml`

4. Click "Run Backup Now" to start backup

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
