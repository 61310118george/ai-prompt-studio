from pathlib import Path

from ai_memory_app.platform_paths import (
    DATA_DIR_ENV,
    DB_PATH_ENV,
    LEGACY_DB_PATH_ENV,
    get_default_db_path,
    resolve_app_data_dir,
)
from ai_memory_app.services.desktop_api import safe_export_filename


def test_windows_uses_local_app_data() -> None:
    result = resolve_app_data_dir(
        platform_name="win32",
        environ={"LOCALAPPDATA": r"C:\Users\tester\AppData\Local"},
        home=Path("C:/Users/tester"),
    )
    assert str(result).replace("\\", "/").endswith("AppData/Local/AI Prompt Studio")


def test_windows_falls_back_when_environment_is_missing(tmp_path: Path) -> None:
    result = resolve_app_data_dir(platform_name="win32", environ={}, home=tmp_path)
    assert result == tmp_path / "AppData" / "Local" / "AI Prompt Studio"


def test_macos_uses_current_directory_for_new_install(tmp_path: Path) -> None:
    result = resolve_app_data_dir(platform_name="darwin", environ={}, home=tmp_path)
    assert result == tmp_path / "Library" / "Application Support" / "AI Prompt Studio"


def test_macos_keeps_legacy_data_directory(tmp_path: Path) -> None:
    legacy = tmp_path / "Library" / "Application Support" / "AI Personal Memory Manager"
    legacy.mkdir(parents=True)
    result = resolve_app_data_dir(platform_name="darwin", environ={}, home=tmp_path)
    assert result == legacy


def test_data_directory_override_has_priority(tmp_path: Path) -> None:
    override = tmp_path / "portable-data"
    result = resolve_app_data_dir(
        platform_name="win32",
        environ={DATA_DIR_ENV: str(override), "LOCALAPPDATA": "ignored"},
        home=tmp_path,
    )
    assert result == override


def test_database_path_accepts_new_and_legacy_overrides(monkeypatch, tmp_path: Path) -> None:
    legacy = tmp_path / "legacy.sqlite3"
    current = tmp_path / "current.sqlite3"
    monkeypatch.setenv(LEGACY_DB_PATH_ENV, str(legacy))
    assert get_default_db_path() == legacy
    monkeypatch.setenv(DB_PATH_ENV, str(current))
    assert get_default_db_path() == current


def test_export_filename_is_windows_safe() -> None:
    assert safe_export_filename('campaign:Q4?*') == "campaign-Q4--"
    assert safe_export_filename("CON") == "_CON"
    assert safe_export_filename("NUL. ") == "_NUL"
    assert safe_export_filename("  ") == "my-prompt"
