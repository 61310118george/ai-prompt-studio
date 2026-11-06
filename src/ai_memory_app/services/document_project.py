"""Validate document drafts and export a new, non-overwriting project folder."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import yaml

from .prompt_workbench import validate_text

TYPES = {'core', 'memory', 'skill'}
STATE_TYPES = TYPES | {'mcp'}


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
    if value.get('mode', '') not in STATE_TYPES | {'', 'project'} or value.get('active', 'core') not in STATE_TYPES:
        raise ValueError('文件類型不正確。')
    if len(json.dumps(value, ensure_ascii=False)) > 800_000:
        raise ValueError('專案草稿過大，請縮短內容。')
    docs = value.get('documents', {})
    if not isinstance(docs, dict) or set(docs) - STATE_TYPES:
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
    topic_drafts = value.get('topicDrafts', {})
    if not isinstance(topic_drafts, dict) or len(topic_drafts) > 20:
        raise ValueError('分類草稿格式不正確。')
    for topic, documents in topic_drafts.items():
        if not isinstance(topic, str) or len(topic) > 200:
            raise ValueError('分類草稿名稱不正確。')
        validate_document_state({'mode': value.get('mode', ''), 'documents': documents})
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


def mcp_server_name(title):
    """Return a cross-platform, package-safe MCP server identifier."""
    name = re.sub(r'[^a-z0-9]+', '-', str(title).lower()).strip('-')[:64].rstrip('-')
    if not name or name == 'mcp':
        name = 'mcp-server'
    if name in {'con', 'prn', 'aux', 'nul', *(f'{prefix}{n}' for prefix in ('com', 'lpt') for n in range(1, 10))}:
        name = f'mcp-{name}'
    return name


def mcp_project_files(project):
    """Build a runnable, deliberately safe MCP Server starter project."""
    if not isinstance(project, dict):
        raise ValueError('MCP 專案格式不正確。')
    title = validate_text(project.get('title', '')).strip()
    content = validate_text(project.get('content', '')).strip()
    fields = project.get('fields', {})
    if not title or not content or not isinstance(fields, dict):
        raise ValueError('請先完成 MCP 表單並建立規格預覽。')
    allowed = {'purpose', 'host', 'tools', 'resources', 'prompts', 'connection',
               'dependencies', 'security', 'verification'}
    if set(fields) - allowed:
        raise ValueError('MCP 欄位格式不正確。')
    clean = {}
    for key, value in fields.items():
        clean[key] = validate_text(value).strip()
        if len(clean[key]) > 20000:
            raise ValueError('MCP 欄位超過長度限制。')
    for key in ('purpose', 'tools', 'connection', 'security', 'verification'):
        if not clean.get(key):
            raise ValueError('請完成 MCP 的用途、Tool、連線、安全及驗收欄位。')

    name = mcp_server_name(title)
    plan_literal = json.dumps(content + '\n', ensure_ascii=False)
    title_literal = json.dumps(title, ensure_ascii=False)
    server = f'''"""Generated MCP starter. Implement real integrations only after reviewing MCP-PLAN.md."""
import logging
import os

from mcp.server import MCPServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = MCPServer({json.dumps(name)})
SERVER_TITLE = {title_literal}
PLAN = {plan_literal}


@mcp.tool()
def get_server_plan() -> str:
    """Read the approved implementation plan before adding real actions."""
    return PLAN


@mcp.resource("guide://server-plan")
def read_server_plan() -> str:
    """Return the MCP Server plan as a read-only resource."""
    return PLAN


@mcp.prompt()
def plan_next_step(goal: str = "") -> str:
    """Create a review prompt for the next implementation step."""
    focus = goal.strip() or "下一個尚未完成的項目"
    return (
        f"請先閱讀 {{SERVER_TITLE}} 的 guide://server-plan，確認 {{focus}} 的資料來源、"
        "輸入輸出、權限與測試方式；資訊不足時先詢問，不要假設已完成串接。"
    )


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport not in {{"stdio", "streamable-http"}}:
        raise SystemExit("MCP_TRANSPORT must be stdio or streamable-http")
    if transport == "streamable-http" and os.getenv("MCP_REMOTE_SECURITY_REVIEWED") != "true":
        raise SystemExit("Remote HTTP is locked until MCP_REMOTE_SECURITY_REVIEWED=true")
    mcp.run(transport=transport)
'''
    readme = f'''# {title} MCP Server

這是 AI Prompt Studio 產生的 MCP 起始專案。它會啟動一個可測試的 Server，並提供安全的示範 Tool、Resource 與 Prompt；`MCP-PLAN.md` 中列出的第三方 API 與業務動作仍須由開發者實作、審查及測試。

MCP 不會取代提示詞：Prompt 說明 AI 如何工作；MCP 讓 AI 透過 Tool 執行動作、透過 Resource 讀取資料，並可提供可重用 Prompt。

## 安裝與啟動

需要 Python 3.10 以上與 `uv`。尚未安裝 `uv` 時，先依官方說明安裝：https://docs.astral.sh/uv/getting-started/installation/

macOS：

```sh
uv sync
uv run server.py
```

Windows 11 PowerShell：

```powershell
uv sync
uv run server.py
```

預設使用本機 `stdio`。請把 `client-config.example.json` 的路徑改成此資料夾的絕對路徑，再加入支援 MCP 的 Host。

## 驗證

```sh
uv run mcp dev server.py
```

逐一確認 `get_server_plan`、`guide://server-plan` 與 `plan_next_step`。完成真實能力後，再用 MCP Inspector 測試正常輸入、錯誤輸入、權限不足及會修改資料的操作。

## 下一步

1. 先讀 `MCP-PLAN.md`，把每個預定 Tool 拆成明確輸入、輸出與副作用。
2. 只讀資料優先做成 Resource；會執行動作的能力才做成 Tool。
3. 金鑰只從環境變數或安全憑證庫讀取，不要寫進程式或設定範例。
4. 發文、刪除、付款等高影響操作保留人工確認。
5. 遠端 Streamable HTTP 上線前完成 OAuth、最小權限、來源驗證與安全審查，再設定 `MCP_TRANSPORT=streamable-http` 及 `MCP_REMOTE_SECURITY_REVIEWED=true`。

## 官方參考

- MCP 架構：https://modelcontextprotocol.io/docs/learn/architecture
- 建立 Server：https://modelcontextprotocol.io/docs/develop/build-server
- MCP Inspector：https://modelcontextprotocol.io/docs/tools/inspector
- 安全建議：https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
'''
    config = json.dumps({'mcpServers': {name: {'command': 'uv', 'args': [
        '--directory', 'REPLACE_WITH_ABSOLUTE_PATH', 'run', 'server.py']} }}, ensure_ascii=False, indent=2) + '\n'
    pyproject = f'''[project]
name = {json.dumps(name)}
version = "0.1.0"
description = {title_literal}
requires-python = ">=3.10"
dependencies = ["mcp[cli]>=2.0.0,<3"]
'''
    environment = '''# 不要把真實金鑰提交到 Git。請依 MCP-PLAN.md 的外部服務自行新增名稱。
EXAMPLE_API_KEY=replace-me
MCP_TRANSPORT=stdio
# 遠端安全審查完成前保持 false
MCP_REMOTE_SECURITY_REVIEWED=false
'''
    return {'README.md': readme, 'MCP-PLAN.md': content + '\n', 'server.py': server,
            'pyproject.toml': pyproject, '.env.example': environment,
            'client-config.example.json': config}


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
