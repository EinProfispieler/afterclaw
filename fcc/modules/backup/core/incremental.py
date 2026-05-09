# fcc/modules/backup/core/incremental.py
import sqlite3
from pathlib import Path
from typing import List
from fcc.modules.backup.utils.hash import compute_file_hash


class HashBasedDetector:
    """Detects file changes using hash comparison with SQLite database."""

    def __init__(self, db_path: str):
        """Initialize detector with database path.

        Args:
            db_path: Path to SQLite database for storing file hashes
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with file_hashes table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_hashes (
                file_path TEXT PRIMARY KEY,
                hash TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def detect_changes(self, file_paths: List[str]) -> List[str]:
        """Detect which files have changed since last scan.

        This is a pure read operation — the hash index is NOT updated
        here. Callers must invoke ``commit_hashes`` for the subset of
        files that were actually backed up successfully. Persisting the
        hash before the copy completes can silently mark unbacked-up
        files as up-to-date if the target write fails partway through.

        Args:
            file_paths: List of file paths to check

        Returns:
            List of file paths that have changed or are new
        """
        changed_files = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            for file_path in file_paths:
                current_hash = compute_file_hash(file_path)

                cursor.execute(
                    "SELECT hash FROM file_hashes WHERE file_path = ?",
                    (file_path,)
                )
                result = cursor.fetchone()

                if result is None or result[0] != current_hash:
                    changed_files.append(file_path)
                # else: unchanged file, do nothing
        finally:
            conn.close()

        return changed_files

    def commit_hashes(self, file_paths: List[str]) -> None:
        """Persist current hashes for files that were successfully backed up.

        Call this AFTER the storage layer reports success for the listed
        files. Files omitted from this list will be re-detected as
        changed on the next run, which is the desired behavior when an
        earlier backup attempt for them failed.

        Args:
            file_paths: List of file paths whose backup succeeded.
        """
        if not file_paths:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for file_path in file_paths:
                # Re-compute hash at commit time to be precise: detect_changes
                # may have been called minutes/hours ago and the file could
                # have changed again — we want the hash that matches what was
                # actually copied. Storage layer should pass back the hash
                # too; for now re-read.
                current_hash = compute_file_hash(file_path)
                cursor.execute(
                    "INSERT INTO file_hashes (file_path, hash) VALUES (?, ?) "
                    "ON CONFLICT(file_path) DO UPDATE SET hash = excluded.hash",
                    (file_path, current_hash)
                )
            conn.commit()
        finally:
            conn.close()
