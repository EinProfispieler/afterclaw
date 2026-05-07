# fcc/modules/backup/utils/hash.py
import hashlib
from pathlib import Path


def compute_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Compute hash of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()
