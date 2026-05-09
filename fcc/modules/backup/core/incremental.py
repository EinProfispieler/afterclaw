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

        Args:
            file_paths: List of file paths to check

        Returns:
            List of file paths that have changed or are new
        """
        changed_files = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for file_path in file_paths:
            # Compute current hash
            current_hash = compute_file_hash(file_path)

            # Check if file exists in database
            cursor.execute(
                "SELECT hash FROM file_hashes WHERE file_path = ?",
                (file_path,)
            )
            result = cursor.fetchone()

            if result is None:
                # New file
                changed_files.append(file_path)
                cursor.execute(
                    "INSERT INTO file_hashes (file_path, hash) VALUES (?, ?)",
                    (file_path, current_hash)
                )
            elif result[0] != current_hash:
                # Modified file
                changed_files.append(file_path)
                cursor.execute(
                    "UPDATE file_hashes SET hash = ? WHERE file_path = ?",
                    (current_hash, file_path)
                )
            # else: unchanged file, do nothing

        conn.commit()
        conn.close()

        return changed_files
