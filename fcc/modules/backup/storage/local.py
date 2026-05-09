# fcc/modules/backup/storage/local.py
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List
from fcc.modules.backup.storage.base import (
    BackupTarget,
    FileInfo,
    SnapshotInfo,
    BackupResult,
    StorageStats
)


class LocalDiskTarget(BackupTarget):
    """Local disk backup target implementation."""

    def __init__(self, backup_root: str):
        """Initialize local disk target.

        Args:
            backup_root: Root directory for backups
        """
        self.backup_root = Path(backup_root)
        self._ensure_structure()

    def _ensure_structure(self):
        """Ensure backup directory structure exists."""
        self.backup_root.mkdir(parents=True, exist_ok=True)
        snapshots_dir = self.backup_root / ".timecapsule" / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

    def check_available(self) -> bool:
        """Check if target is available.

        Returns:
            True if backup root is accessible
        """
        try:
            self.backup_root.mkdir(parents=True, exist_ok=True)
            return self.backup_root.exists() and self.backup_root.is_dir()
        except Exception:
            return False

    def backup(self, files: List[FileInfo], snapshot_id: str) -> BackupResult:
        """Execute backup to local disk.

        Args:
            files: List of files to backup
            snapshot_id: Unique identifier for this snapshot

        Returns:
            BackupResult with operation details
        """
        errors = []
        files_processed = 0
        bytes_transferred = 0

        # Create snapshot directory
        snapshot_dir = self.backup_root / ".timecapsule" / "snapshots" / snapshot_id
        files_dir = snapshot_dir / "files"

        try:
            files_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return BackupResult(
                success=False,
                files_processed=0,
                bytes_transferred=0,
                errors=[f"Failed to create snapshot directory: {str(e)}"]
            )

        # Copy files
        succeeded_files = []
        for file_info in files:
            try:
                source_path = Path(file_info.path)
                if not source_path.exists():
                    errors.append(f"Source file not found: {file_info.path}")
                    continue

                # Mirror the absolute source path under files/ so that two
                # files with the same basename in different source dirs do
                # NOT overwrite each other (e.g. ~/Projects/README.md and
                # ~/Documents/README.md both used to land at files/README.md).
                # We strip the path anchor ("/" on Unix, "C:\\" on Windows)
                # so the destination stays inside files_dir.
                if source_path.is_absolute():
                    relative_anchor = Path(*source_path.parts[1:])
                else:
                    relative_anchor = source_path
                dest_path = files_dir / relative_anchor
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(source_path, dest_path)
                files_processed += 1
                bytes_transferred += file_info.size
                succeeded_files.append(file_info.path)
            except Exception as e:
                errors.append(f"Failed to backup {file_info.path}: {str(e)}")

        # Create manifest
        manifest = {
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now().isoformat(),
            "files": [
                {
                    "path": f.path,
                    "category": f.category,
                    "size": f.size,
                    "hash": f.hash
                }
                for f in files
            ],
            "files_processed": files_processed,
            "bytes_transferred": bytes_transferred
        }

        try:
            manifest_path = snapshot_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            errors.append(f"Failed to write manifest: {str(e)}")

        return BackupResult(
            success=(files_processed > 0 and len(errors) == 0),
            files_processed=files_processed,
            bytes_transferred=bytes_transferred,
            errors=errors,
            succeeded_files=succeeded_files,
        )

    def list_snapshots(self) -> List[SnapshotInfo]:
        """List all snapshots.

        Returns:
            List of SnapshotInfo objects sorted by timestamp
        """
        snapshots = []
        snapshots_dir = self.backup_root / ".timecapsule" / "snapshots"

        if not snapshots_dir.exists():
            return snapshots

        for snapshot_dir in sorted(snapshots_dir.iterdir()):
            if not snapshot_dir.is_dir():
                continue

            manifest_path = snapshot_dir / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                snapshots.append(SnapshotInfo(
                    id=manifest["snapshot_id"],
                    timestamp=datetime.fromisoformat(manifest["timestamp"]),
                    file_count=manifest["files_processed"],
                    total_size=manifest["bytes_transferred"]
                ))
            except Exception:
                # Skip corrupted manifests
                continue

        return sorted(snapshots, key=lambda s: s.timestamp)

    def get_storage_usage(self) -> StorageStats:
        """Get storage usage statistics.

        Returns:
            StorageStats with usage information
        """
        snapshots = self.list_snapshots()

        if not snapshots:
            return StorageStats(
                total_size=0,
                snapshot_count=0,
                oldest_snapshot=datetime.now(),
                newest_snapshot=datetime.now()
            )

        total_size = sum(s.total_size for s in snapshots)
        oldest = min(s.timestamp for s in snapshots)
        newest = max(s.timestamp for s in snapshots)

        return StorageStats(
            total_size=total_size,
            snapshot_count=len(snapshots),
            oldest_snapshot=oldest,
            newest_snapshot=newest
        )
