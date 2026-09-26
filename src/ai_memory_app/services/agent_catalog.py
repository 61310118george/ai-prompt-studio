from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path


def application_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[3]


def catalog_path() -> Path:
    return application_root() / "resources" / "agent_catalog" / "v1" / "catalog.json"


@lru_cache(maxsize=1)
def load_agent_catalog() -> dict:
    with catalog_path().open(encoding="utf-8") as handle:
        return json.load(handle)


def get_agent(agent_id: str) -> dict:
    for agent in load_agent_catalog()["agents"]:
        if agent["id"] == agent_id:
            return agent
    raise ValueError(f"不支援的 Agent：{agent_id}")


def get_file_type(agent_id: str, file_type_id: str) -> dict:
    for file_type in get_agent(agent_id)["files"]:
        if file_type["id"] == file_type_id:
            return file_type
    raise ValueError(f"{agent_id} 不支援檔案類型：{file_type_id}")


def get_module(module_id: str) -> dict:
    for module in load_agent_catalog()["modules"]:
        if module["id"] == module_id:
            return module
    raise ValueError(f"找不到記憶模組：{module_id}")
