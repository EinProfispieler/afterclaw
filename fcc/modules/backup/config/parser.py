"""Configuration parser for backup module."""

import yaml
from pathlib import Path
from typing import Dict, Any


DEFAULT_CONFIG = {
    "version": "1.0",
    "sources": [],
    "targets": {
        "local": {
            "enabled": False,
            "path": ""
        }
    },
    "retention": {
        "daily": 7,
        "weekly": 4,
        "monthly": 12,
        "yearly": 5
    },
    "compression": {
        "enabled": True,
        "level": 6
    },
    "encryption": {
        "enabled": False,
        "algorithm": "AES-256"
    }
}


class ConfigParser:
    """Parser for backup configuration files."""

    def __init__(self):
        """Initialize the configuration parser."""
        self.default_config = DEFAULT_CONFIG.copy()

    def parse(self, config_path: str) -> Dict[str, Any]:
        """
        Parse a YAML configuration file and merge with defaults.

        Args:
            config_path: Path to the configuration file

        Returns:
            Parsed configuration dictionary with defaults applied

        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the configuration file is invalid YAML
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_file, 'r') as f:
            user_config = yaml.safe_load(f)

        if user_config is None:
            user_config = {}

        # Merge user config with defaults
        merged_config = self._merge_with_defaults(user_config, self.default_config)

        return merged_config

    def _merge_with_defaults(self, user_config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge user configuration with default configuration.

        Args:
            user_config: User-provided configuration
            defaults: Default configuration

        Returns:
            Merged configuration dictionary
        """
        result = defaults.copy()

        for key, value in user_config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._merge_with_defaults(value, result[key])
            else:
                # Override with user value
                result[key] = value

        return result
