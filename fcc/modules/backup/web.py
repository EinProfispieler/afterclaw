"""Backup module for AfterClaw - Web API and UI integration."""

import json
import os
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Any

from fcc.config import app_root, load_app_config
from fcc.modules import Module, register
from fcc.modules.backup.core.file_classifier import FileClassifier, FileCategory
from fcc.modules.backup.core.incremental import HashBasedDetector
from fcc.modules.backup.storage.base import FileInfo
from fcc.modules.backup.storage.local import LocalDiskTarget
from fcc.modules.backup.config.parser import ConfigParser
from fcc.modules.backup.utils.logger import setup_logger

logger = setup_logger("backup")

module = Module(
    name="backup",
    display_name="Backup",
    description="Directory-level backup orchestration"
)


def _get_backup_config_path() -> Path:
    """Get backup configuration file path."""
    return app_root() / "data" / "backup_config.yaml"


def _get_backup_db_path() -> Path:
    """Get backup database path."""
    return app_root() / "data" / "backup_index.db"


def _ensure_default_config():
    """Ensure default backup configuration exists."""
    config_path = _get_backup_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not config_path.exists():
        default_config = """version: "1.0"

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
"""
        config_path.write_text(default_config)


def handle_backup_status(handler, path: str, params: dict, body: Any) -> None:
    """Handle GET /api/backup/status - Get backup status."""
    try:
        _ensure_default_config()
        config_path = _get_backup_config_path()
        db_path = _get_backup_db_path()
        
        parser = ConfigParser()
        cfg = parser.parse(str(config_path))
        
        # Get storage stats if local target is enabled
        stats = None
        if cfg["targets"]["local"]["enabled"]:
            target_path = Path(cfg["targets"]["local"]["path"]).expanduser()
            target = LocalDiskTarget(str(target_path))
            storage_stats = target.get_storage_usage()
            stats = {
                "total_size": storage_stats.total_size,
                "snapshot_count": storage_stats.snapshot_count,
                "oldest_snapshot": storage_stats.oldest_snapshot.isoformat() if storage_stats.snapshot_count > 0 else None,
                "newest_snapshot": storage_stats.newest_snapshot.isoformat() if storage_stats.snapshot_count > 0 else None,
            }
        
        response = {
            "success": True,
            "config_path": str(config_path),
            "db_path": str(db_path),
            "db_exists": db_path.exists(),
            "storage_stats": stats,
        }
        
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(response).encode())
    except Exception as e:
        logger.error(f"Error getting backup status: {e}")
        handler.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())


def handle_backup_run(handler, path: str, params: dict, body: Any) -> None:
    """Handle POST /api/backup/run - Run backup."""
    try:
        _ensure_default_config()
        config_path = _get_backup_config_path()
        
        parser = ConfigParser()
        cfg = parser.parse(str(config_path))
        
        # Initialize components
        db_path = _get_backup_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        classifier = FileClassifier()
        detector = HashBasedDetector(str(db_path))
        
        # Collect files
        all_files = []
        for source in cfg["sources"]:
            source_path = Path(source["path"]).expanduser()
            if not source_path.exists():
                logger.warning(f"Source path does not exist: {source_path}")
                continue
            
            for file_path in source_path.rglob("*"):
                if file_path.is_file() and not classifier.should_exclude(str(file_path)):
                    all_files.append(str(file_path))
        
        # Detect changes
        changed_files = detector.detect_changes(all_files)
        
        if not changed_files:
            response = {
                "success": True,
                "message": "No changes detected",
                "files_processed": 0,
                "bytes_transferred": 0,
            }
            handler.send_response(HTTPStatus.OK)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(response).encode())
            return
        
        # Prepare file info
        file_infos = []
        for file_path in changed_files:
            path = Path(file_path)
            category = classifier.classify(file_path)
            from fcc.modules.backup.utils.hash import compute_file_hash
            file_infos.append(FileInfo(
                path=file_path,
                category=category.value,
                size=path.stat().st_size,
                hash=compute_file_hash(file_path)
            ))
        
        # Backup to local target
        if cfg["targets"]["local"]["enabled"]:
            target_path = Path(cfg["targets"]["local"]["path"]).expanduser()
            target = LocalDiskTarget(str(target_path))
            
            snapshot_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            result = target.backup(file_infos, snapshot_id)
            
            response = {
                "success": result.success,
                "files_processed": result.files_processed,
                "bytes_transferred": result.bytes_transferred,
                "errors": result.errors,
                "snapshot_id": snapshot_id,
            }
        else:
            response = {
                "success": False,
                "error": "No backup target enabled",
            }
        
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(response).encode())
    except Exception as e:
        logger.error(f"Error running backup: {e}")
        handler.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())


def handle_backup_list(handler, path: str, params: dict, body: Any) -> None:
    """Handle GET /api/backup/list - List snapshots."""
    try:
        _ensure_default_config()
        config_path = _get_backup_config_path()
        
        parser = ConfigParser()
        cfg = parser.parse(str(config_path))
        
        snapshots = []
        if cfg["targets"]["local"]["enabled"]:
            target_path = Path(cfg["targets"]["local"]["path"]).expanduser()
            target = LocalDiskTarget(str(target_path))
            
            snapshot_infos = target.list_snapshots()
            snapshots = [
                {
                    "id": s.id,
                    "timestamp": s.timestamp.isoformat(),
                    "file_count": s.file_count,
                    "total_size": s.total_size,
                }
                for s in snapshot_infos
            ]
        
        response = {
            "success": True,
            "snapshots": snapshots,
        }
        
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(response).encode())
    except Exception as e:
        logger.error(f"Error listing snapshots: {e}")
        handler.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())


def handle_backup_page(handler, path: str, params: dict, body: Any) -> None:
    """Handle GET /backup - Backup management page."""
    from fcc.web.renderer import render_page
    
    html = render_page(
        title="Backup",
        body_content=_render_backup_page(),
        active_nav="backup"
    )
    
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(html.encode())


def _render_backup_page() -> str:
    """Render backup management page content."""
    return """
    <div class="container mt-4">
        <h2>Backup Management</h2>
        
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Backup Status</h5>
                    </div>
                    <div class="card-body" id="backup-status">
                        <p class="text-muted">Loading...</p>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Actions</h5>
                    </div>
                    <div class="card-body">
                        <button class="btn btn-primary" id="run-backup-btn">
                            <i class="bi bi-play-fill"></i> Run Backup Now
                        </button>
                        <div id="backup-result" class="mt-3"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h5>Snapshots</h5>
                    </div>
                    <div class="card-body">
                        <div id="snapshots-list">
                            <p class="text-muted">Loading...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function loadBackupStatus() {
        fetch('/api/backup/status')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const stats = data.storage_stats;
                    let html = '<dl class="row">';
                    html += '<dt class="col-sm-4">Config Path:</dt><dd class="col-sm-8"><code>' + data.config_path + '</code></dd>';
                    html += '<dt class="col-sm-4">Database:</dt><dd class="col-sm-8">' + (data.db_exists ? '✓ Exists' : '✗ Not initialized') + '</dd>';
                    
                    if (stats) {
                        html += '<dt class="col-sm-4">Snapshots:</dt><dd class="col-sm-8">' + stats.snapshot_count + '</dd>';
                        html += '<dt class="col-sm-4">Total Size:</dt><dd class="col-sm-8">' + formatBytes(stats.total_size) + '</dd>';
                        if (stats.newest_snapshot) {
                            html += '<dt class="col-sm-4">Last Backup:</dt><dd class="col-sm-8">' + new Date(stats.newest_snapshot).toLocaleString() + '</dd>';
                        }
                    }
                    
                    html += '</dl>';
                    document.getElementById('backup-status').innerHTML = html;
                } else {
                    document.getElementById('backup-status').innerHTML = '<p class="text-danger">Error: ' + data.error + '</p>';
                }
            })
            .catch(err => {
                document.getElementById('backup-status').innerHTML = '<p class="text-danger">Error loading status</p>';
            });
    }
    
    function loadSnapshots() {
        fetch('/api/backup/list')
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    if (data.snapshots.length === 0) {
                        document.getElementById('snapshots-list').innerHTML = '<p class="text-muted">No snapshots found</p>';
                        return;
                    }
                    
                    let html = '<table class="table table-striped"><thead><tr>';
                    html += '<th>Snapshot ID</th><th>Timestamp</th><th>Files</th><th>Size</th>';
                    html += '</tr></thead><tbody>';
                    
                    data.snapshots.forEach(s => {
                        html += '<tr>';
                        html += '<td><code>' + s.id + '</code></td>';
                        html += '<td>' + new Date(s.timestamp).toLocaleString() + '</td>';
                        html += '<td>' + s.file_count + '</td>';
                        html += '<td>' + formatBytes(s.total_size) + '</td>';
                        html += '</tr>';
                    });
                    
                    html += '</tbody></table>';
                    document.getElementById('snapshots-list').innerHTML = html;
                } else {
                    document.getElementById('snapshots-list').innerHTML = '<p class="text-danger">Error: ' + data.error + '</p>';
                }
            })
            .catch(err => {
                document.getElementById('snapshots-list').innerHTML = '<p class="text-danger">Error loading snapshots</p>';
            });
    }
    
    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    document.getElementById('run-backup-btn').addEventListener('click', function() {
        const btn = this;
        const resultDiv = document.getElementById('backup-result');
        
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
        resultDiv.innerHTML = '';
        
        fetch('/api/backup/run', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Backup Now';
                
                if (data.success) {
                    let html = '<div class="alert alert-success">';
                    html += '<strong>Backup completed!</strong><br>';
                    html += 'Files processed: ' + data.files_processed + '<br>';
                    html += 'Bytes transferred: ' + formatBytes(data.bytes_transferred);
                    if (data.snapshot_id) {
                        html += '<br>Snapshot ID: <code>' + data.snapshot_id + '</code>';
                    }
                    html += '</div>';
                    resultDiv.innerHTML = html;
                    
                    // Reload status and snapshots
                    loadBackupStatus();
                    loadSnapshots();
                } else {
                    let html = '<div class="alert alert-danger">';
                    html += '<strong>Backup failed!</strong><br>';
                    html += data.error || 'Unknown error';
                    if (data.errors && data.errors.length > 0) {
                        html += '<ul class="mt-2 mb-0">';
                        data.errors.forEach(e => html += '<li>' + e + '</li>');
                        html += '</ul>';
                    }
                    html += '</div>';
                    resultDiv.innerHTML = html;
                }
            })
            .catch(err => {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Backup Now';
                resultDiv.innerHTML = '<div class="alert alert-danger">Error running backup</div>';
            });
    });
    
    // Load initial data
    loadBackupStatus();
    loadSnapshots();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        loadBackupStatus();
        loadSnapshots();
    }, 30000);
    </script>
    """


# Register routes
module.add_route("GET", "/backup", handle_backup_page)
module.add_route("GET", "/api/backup/status", handle_backup_status)
module.add_route("POST", "/api/backup/run", handle_backup_run)
module.add_route("GET", "/api/backup/list", handle_backup_list)

# Register module
register(module)
