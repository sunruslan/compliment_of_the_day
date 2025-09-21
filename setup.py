"""
Centralized setup module for the compliment bot application.
Handles logging configuration, environment variable loading, and config management.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


# Global config variable
_config: Dict[str, Any] = {}


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to the config file

    Returns:
        Configuration dictionary
    """
    global _config

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f)

    return _config


def get_config(key: str = None, default: Any = None) -> Any:
    """
    Get configuration value by key path (e.g., 'database.name').

    Args:
        key: Configuration key path (dot notation)
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    if not _config:
        load_config()

    if key is None:
        return _config

    keys = key.split(".")
    value = _config

    try:
        for k in keys:
            value = value[k]
        return value
    except (KeyError, TypeError):
        return default


def setup_logging(level: int = None, format_string: str = None) -> None:
    """
    Configure logging for the application.

    Args:
        level: Logging level (default: from config or INFO)
        format_string: Custom format string for log messages (default: from config)
    """
    if level is None:
        level_str = get_config("logging.level", "INFO")
        level = getattr(logging, level_str.upper(), logging.INFO)

    if format_string is None:
        format_string = get_config(
            "logging.format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    logging.basicConfig(level=level, format=format_string)


def setup_environment() -> None:
    """
    Load environment variables from .env file.
    """
    load_dotenv()


def setup_application(config_path: str = "config.yaml") -> None:
    """
    Complete application setup including config, logging and environment variables.
    Call this function at the start of your application.

    Args:
        config_path: Path to the config file
    """
    load_config(config_path)
    setup_environment()
    setup_logging()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
