"""File classification module for backup."""

import os
from enum import Enum
from pathlib import Path
from typing import Union


class FileCategory(Enum):
    """Categories for file classification."""
    CODE = "code"
    AI = "ai"
    MEDIA = "media"
    LARGE = "large"
    DOCUMENT = "document"
    OTHER = "other"


class FileClassifier:
    """Classifies files into categories for backup processing."""

    # File size threshold for LARGE category (50MB)
    LARGE_FILE_THRESHOLD = 50 * 1024 * 1024

    # Extension mappings
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.c', '.cpp',
        '.h', '.hpp', '.cs', '.rb', '.php', '.swift', '.kt', '.scala', '.sh',
        '.bash', '.zsh', '.fish', '.ps1', '.r', '.m', '.mm', '.dart', '.lua',
        '.pl', '.pm', '.sql', '.html', '.css', '.scss', '.sass', '.less',
        '.vue', '.svelte', '.elm', '.ex', '.exs', '.erl', '.hrl', '.clj',
        '.cljs', '.cljc', '.ml', '.mli', '.fs', '.fsx', '.fsi', '.vb',
        '.asm', '.s', '.v', '.vhd', '.vhdl', '.sv', '.svh'
    }

    MEDIA_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico',
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v',
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
        '.pdf', '.psd', '.ai', '.sketch', '.fig', '.xd'
    }

    # AI-related path patterns
    AI_PATTERNS = {
        '.claude', '.cursor', '.aider', '.continue', '.windsurf',
        'prompts', '.prompts', 'ai-context', '.ai'
    }

    # Directories to exclude
    EXCLUDE_PATTERNS = {
        'node_modules', '.git', '.svn', '.hg', '__pycache__', '.pytest_cache',
        '.mypy_cache', '.tox', '.nox', 'venv', '.venv', 'env', '.env',
        'dist', 'build', '.next', '.nuxt', 'target', 'bin', 'obj',
        '.gradle', '.idea', '.vscode', '.DS_Store', 'coverage',
        '.coverage', 'htmlcov', '.eggs', '*.egg-info'
    }

    def __init__(self):
        """Initialize the FileClassifier."""
        pass

    def classify(self, file_path: Union[str, Path]) -> FileCategory:
        """
        Classify a file into a category.

        Args:
            file_path: Path to the file to classify

        Returns:
            FileCategory enum value
        """
        file_path = Path(file_path)

        # Check if file is large (must check size first if file exists)
        if file_path.exists() and file_path.is_file():
            if file_path.stat().st_size > self.LARGE_FILE_THRESHOLD:
                return FileCategory.LARGE

        # Check if file is in AI-related directory
        if self._is_ai_file(file_path):
            return FileCategory.AI

        # Check file extension
        extension = file_path.suffix.lower()

        if extension in self.CODE_EXTENSIONS:
            return FileCategory.CODE

        if extension in self.MEDIA_EXTENSIONS:
            return FileCategory.MEDIA

        # Default to OTHER
        return FileCategory.OTHER

    def should_exclude(self, file_path: Union[str, Path]) -> bool:
        """
        Determine if a file should be excluded from processing.

        Args:
            file_path: Path to check

        Returns:
            True if file should be excluded, False otherwise
        """
        file_path = Path(file_path)
        parts = file_path.parts

        # Check if any part of the path matches exclude patterns
        for part in parts:
            if part in self.EXCLUDE_PATTERNS:
                return True
            # Handle glob patterns like *.egg-info
            for pattern in self.EXCLUDE_PATTERNS:
                if '*' in pattern:
                    pattern_base = pattern.replace('*', '')
                    if pattern_base in part:
                        return True

        return False

    def _is_ai_file(self, file_path: Path) -> bool:
        """
        Check if file is AI-related based on path patterns.

        Args:
            file_path: Path to check

        Returns:
            True if file is AI-related, False otherwise
        """
        parts = file_path.parts

        for part in parts:
            if part in self.AI_PATTERNS:
                return True

        return False
