from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path


APP_DIRECTORY_NAME = "AI Prompt Studio"
LEGACY_MACOS_DIRECTORY_NAME = "AI Personal Memory Manager"
DATABASE_FILENAME = "ai_memory_app.sqlite3"
DATA_DIR_ENV = "AI_PROMPT_STUDIO_DATA_DIR"
DB_PATH_ENV = "AI_PROMPT_STUDIO_DB_PATH"
LEGACY_DB_PATH_ENV = "AI_MEMORY_APP_DB_PATH"


def resolve_app_data_dir(
    *,
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the per-user writable data directory for the current platform."""
    platform_name = platform_name or sys.platform
    environ = os.environ if environ is None else environ
    home = (home or Path.home()).expanduser()

    override = environ.get(DATA_DIR_ENV)
    if override:
        return Path(override).expanduser()

    if platform_name == "win32":
        base = environ.get("LOCALAPPDATA") or environ.get("APPDATA")
        return (Path(base).expanduser() if base else home / "AppData" / "Local") / APP_DIRECTORY_NAME

    if platform_name == "darwin":
        application_support = home / "Library" / "Application Support"
        current = application_support / APP_DIRECTORY_NAME
        legacy = application_support / LEGACY_MACOS_DIRECTORY_NAME
        if legacy.exists() and not current.exists():
            return legacy
        return current

    data_home = environ.get("XDG_DATA_HOME")
    return (Path(data_home).expanduser() if data_home else home / ".local" / "share") / APP_DIRECTORY_NAME


def get_app_data_dir() -> Path:
    return resolve_app_data_dir()


def get_default_db_path() -> Path:
    override = os.environ.get(DB_PATH_ENV) or os.environ.get(LEGACY_DB_PATH_ENV)
    return Path(override).expanduser() if override else get_app_data_dir() / DATABASE_FILENAME


def get_backup_dir() -> Path:
    return get_app_data_dir() / "backups"


def get_credential_path() -> Path:
    return get_app_data_dir() / "local_api_credentials.json"


def platform_label() -> str:
    if sys.platform == "win32":
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    return sys.platform
