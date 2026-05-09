# fcc/modules/backup/storage/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime


@dataclass
class FileInfo:
    """Information about a file to backup."""
    path: str
    category: str
    size: int
    hash: str


@dataclass
class SnapshotInfo:
    """Information about a backup snapshot."""
    id: str
    timestamp: datetime
    file_count: int
    total_size: int


@dataclass
class BackupResult:
    """Result of a backup operation."""
    success: bool
    files_processed: int
    bytes_transferred: int
    errors: List[str]


@dataclass
class StorageStats:
    """Storage usage statistics."""
    total_size: int
    snapshot_count: int
    oldest_snapshot: datetime
    newest_snapshot: datetime


class BackupTarget(ABC):
    """Abstract base class for backup targets."""

    @abstractmethod
    def check_available(self) -> bool:
        """Check if target is available."""
        pass

    @abstractmethod
    def backup(self, files: List[FileInfo], snapshot_id: str) -> BackupResult:
        """Execute backup."""
        pass

    @abstractmethod
    def list_snapshots(self) -> List[SnapshotInfo]:
        """List all snapshots."""
        pass

    @abstractmethod
    def get_storage_usage(self) -> StorageStats:
        """Get storage usage statistics."""
        pass
