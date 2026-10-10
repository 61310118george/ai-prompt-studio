"""Per-user local storage for optional third-party API credentials."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ai_memory_app.platform_paths import get_credential_path


class LocalCredentialStore:
    """Store one user's optional API key outside the app and project folders."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_credential_path()

    def load(self) -> str:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return ""
        except (OSError, json.JSONDecodeError, UnicodeError) as exc:
            raise OSError("無法讀取本機 App 的 API 設定。") from exc
        value = payload.get("gemini_api_key", "") if isinstance(payload, dict) else ""
        return value if isinstance(value, str) else ""

    def save(self, secret: str) -> None:
        if not isinstance(secret, str) or not secret:
            raise ValueError("API Key 不能是空白。")
        descriptor = -1
        temporary_name = ""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=".api-key-", suffix=".tmp", dir=self.path.parent)
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                descriptor = -1
                json.dump({"gemini_api_key": secret}, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            if os.name != "nt":
                os.chmod(self.path, 0o600)
        except OSError as exc:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_name:
                try:
                    Path(temporary_name).unlink(missing_ok=True)
                except OSError:
                    pass
            raise OSError("無法將 API Key 儲存至本機 App 設定。") from exc

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise OSError("無法移除本機 App 的 API Key。") from exc
