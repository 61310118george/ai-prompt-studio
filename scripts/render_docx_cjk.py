"""Run the bundled DOCX renderer with a CJK font in its temporary profile."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path


RENDERER = Path("/Users/baizijing/.codex/plugins/cache/openai-primary-runtime/documents/26.909.12148/skills/documents/render_docx.py")
FONT = Path(__file__).resolve().parents[1] / "resources" / "fonts" / "NotoSansTC-VF.ttf"
spec = importlib.util.spec_from_file_location("bundled_render_docx", RENDERER)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
original_build_env = module._build_lo_env


def build_env_with_font(user_profile: str):
    for relative in (Path("Library/Fonts"), Path(".fonts"), Path(".local/share/fonts")):
        folder = Path(user_profile) / relative
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(FONT, folder / FONT.name)
    env = original_build_env(user_profile)
    env["SAL_FONTPATH"] = str(FONT.parent)
    return env


module._build_lo_env = build_env_with_font
module.main()
