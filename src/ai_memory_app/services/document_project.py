"""Validate document drafts and export a new, non-overwriting project folder."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml

from .prompt_workbench import validate_text

TYPES = {'core', 'memory', 'skill'}


def validate_document_state(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            raise ValueError('文件草稿格式不正確。') from None
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError('文件草稿格式不正確。')
    if not value:
        return {}
    if not isinstance(value.get('mode', ''), str) or not isinstance(value.get('active', 'core'), str):
        raise ValueError('文件類型不正確。')
    if value.get('mode', '') not in TYPES | {'', 'project'} or value.get('active', 'core') not in TYPES:
        raise ValueError('文件類型不正確。')
    if len(json.dumps(value, ensure_ascii=False)) > 800_000:
        raise ValueError('專案草稿過大，請縮短內容。')
    docs = value.get('documents', {})
    if not isinstance(docs, dict) or set(docs) - TYPES:
        raise ValueError('專案文件格式不正確。')
    for doc in docs.values():
        if not isinstance(doc, dict) or not isinstance(doc.get('fields', {}), dict):
            raise ValueError('文件欄位格式不正確。')
        validate_text(doc.get('content', ''))
        if any(not isinstance(text, str) or len(text) > 20000 for text in doc.get('fields', {}).values()):
            raise ValueError('文件欄位超過長度限制。')
    if not isinstance(value.get('major', ''), str) or not isinstance(value.get('minors', []), list):
        raise ValueError('分類格式不正確。')
    if any(not isinstance(tag, str) for tag in value.get('minors', [])):
        raise ValueError('分類格式不正確。')
    return value


def skill_name(content):
    lines = content.replace('\r\n', '\n').splitlines()
    if not lines or lines[0] != '---':
        raise ValueError('Skill 必須包含 YAML 格式的 name 與 description。')
    try:
        end = lines.index('---', 1)
        if end > 100:
            raise ValueError('Skill 中繼資料過長。')
        metadata = yaml.safe_load('\n'.join(lines[1:end]))
    except (ValueError, yaml.YAMLError):
        raise ValueError('Skill 的 YAML 中繼資料格式不正確。') from None
    if not isinstance(metadata, dict):
        raise ValueError('Skill 中繼資料必須是欄位物件。')
    name, description = metadata.get('name'), metadata.get('description')
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or len(name) > 64:
        raise ValueError('Skill name 限 1–64 字的小寫英數與單一連字號。')
    if name in {'con', 'prn', 'aux', 'nul', *(f'{prefix}{n}' for prefix in ('com', 'lpt') for n in range(1, 10))}:
        raise ValueError('Skill name 不可使用 Windows 保留名稱。')
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        raise ValueError('Skill description 必須為 1–1,024 字。')
    if not '\n'.join(lines[end+1:]).strip():
        raise ValueError('Skill 執行內容不可空白。')
    return name


def project_files(documents):
    if not isinstance(documents, dict) or set(documents) != TYPES:
        raise ValueError('請完成核心文件、AI 記憶及技能 Skill 三份文件。')
    texts = {key: validate_text(value) for key, value in documents.items()}
    if any(not text.strip() for text in texts.values()):
        raise ValueError('三份文件皆須有內容，才可輸出專案。')
    name = skill_name(texts['skill'])
    skill_path = f'.agents/skills/{name}/SKILL.md'
    routing = f'\n\n## 專案文件索引\n\n- 工作前閱讀 [背景與偏好](memory/CONTEXT.md)。\n- 任務符合技能用途時，閱讀 [技能流程]({skill_path})。\n'
    return {'AGENTS.md': texts['core'].rstrip() + routing,
            'memory/CONTEXT.md': texts['memory'], skill_path: texts['skill']}


def write_project(parent: Path, folder_name: str, files: dict):
    if not folder_name or folder_name in {'.', '..'} or any(char in folder_name for char in '/\\:'):
        raise ValueError('專案資料夾名稱不正確。')
    for relative in files:
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
            raise ValueError('專案文件路徑不正確。')
    # Claim a new directory exclusively; never overwrite or follow an existing target.
    for number in range(1, 1001):
        target = parent / (folder_name if number == 1 else f'{folder_name} ({number})')
        try:
            target.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('已有太多同名資料夾，請改用其他名稱。')
    try:
        for relative, content in files.items():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('x', encoding='utf-8', newline='\n') as handle:
                handle.write(content)
    except Exception:
        shutil.rmtree(target)
        raise
    return {'path': str(target), 'files': list(files)}
