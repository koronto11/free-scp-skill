"""
Shared configuration utilities for free-scp-skill.
Provides data-dir resolution and persistent user configuration.
"""

import json
import os
from pathlib import Path

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DATA_SOURCE = "https://scp-data.tedivm.com"


def get_data_dir():
    """Return the per-user data directory for raw JSON caches and logs."""
    home = Path.home()
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", home)) / "free-scp-skill"
    else:
        base = home / ".local" / "share" / "free-scp-skill"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_dir():
    """Return the per-user configuration directory."""
    home = Path.home()
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", home)) / "free-scp-skill"
    else:
        base = home / ".config" / "free-scp-skill"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_path():
    return get_config_dir() / "config.json"


def get_default_vector_db_path():
    return str(get_data_dir() / "vector_db")


def get_config():
    """
    Load user configuration. Returns a dict with defaults filled in.
    Keys:
      - vector_db_path: str
      - embedding_model: str
      - data_source: str
      - config_version: str
    """
    defaults = {
        "vector_db_path": get_default_vector_db_path(),
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "data_source": DEFAULT_DATA_SOURCE,
        "config_version": "1.0",
    }

    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            defaults.update(user_cfg)
        except (json.JSONDecodeError, OSError):
            pass

    return defaults


def save_config(cfg: dict):
    """Persist configuration to the user's config directory."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
