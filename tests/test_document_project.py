import json
from pathlib import Path

import pytest

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.prompt_library import PromptLibrary
from ai_memory_app.services.document_project import mcp_project_files, project_files, skill_name, validate_document_state, write_project


def documents(name='project-workflow'):
    return {'core': '# Rules\nKeep approved scope.', 'memory': '# Context\nKnown facts.',
            'skill': f'---\nname: {name}\ndescription: "When asked to review"\n---\n\n# Review\nCheck facts.'}


def test_export_links_unicode_collision_and_preserves_existing(tmp_path):
    files = project_files(documents())
    assert 'memory/CONTEXT.md' in files['AGENTS.md']
    assert '.agents/skills/project-workflow/SKILL.md' in files['AGENTS.md']
    first = write_project(tmp_path, '中文專案', files)
    second = write_project(tmp_path, '中文專案', files)
    assert Path(second['path']).name == '中文專案 (2)'
    for relative, content in files.items():
        assert (Path(first['path']) / relative).read_text(encoding='utf-8') == content


@pytest.mark.parametrize('name', ['../escape', 'Invalid', 'two--hyphens', 'a'*65, 'con', 'com1', 'lpt9'])
def test_rejects_invalid_and_windows_reserved_skill_names(name):
    with pytest.raises(ValueError):
        project_files(documents(name))


@pytest.mark.parametrize('text', ['# no metadata', '---\nname: review\n---\nbody',
                                 '---\nname: review\ndescription: test\n---',
                                 '---\nname: [broken\n---\nbody'])
def test_skill_validation(text):
    with pytest.raises(ValueError):
        skill_name(text)


def test_export_requires_all_documents_and_safe_paths(tmp_path):
    with pytest.raises(ValueError):
        project_files({'core': 'test'})
    with pytest.raises(ValueError):
        project_files({**documents(), 'memory': ''})
    with pytest.raises(ValueError):
        write_project(tmp_path, 'test', {'../escape': 'no'})
    assert list(tmp_path.iterdir()) == []


def test_export_failure_removes_only_new_directory(tmp_path, monkeypatch):
    (tmp_path / 'keep').mkdir()
    def fail(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(Path, 'open', fail)
    with pytest.raises(OSError):
        write_project(tmp_path, 'test', project_files(documents()))
    assert [p.name for p in tmp_path.iterdir()] == ['keep']


def test_document_state_roundtrip_and_migration(tmp_path):
    db = tmp_path / 'test.db'
    initialize_database(db)
    initialize_database(db)
    library = PromptLibrary(db)
    state = {'mode': 'project', 'active': 'core', 'major': '開發程式', 'minors': ['寫網頁'],
             'documents': {key: {'fields': {}, 'content': text} for key, text in documents().items()}}
    request = {'title': 'Project', 'content': documents()['core'], 'document_state': state}
    library.save_draft('local', request)
    assert library.load_draft('local')['document_state'] == state
    saved = library.save('local', request)
    assert json.loads(saved['document_state']) == state
    assert validate_document_state(saved['document_state']) == state


def test_mcp_project_is_runnable_scaffold_and_cross_platform():
    project = {
        'title': '社群資料 MCP',
        'content': '# 社群資料 MCP\n\n## Tools\n\n查詢貼文',
        'fields': {
            'purpose': '讀取成效資料', 'tools': '查詢貼文成效',
            'connection': '本機 stdio', 'security': '禁止客戶個資',
            'verification': '使用 Inspector 測試',
        },
    }
    files = mcp_project_files(project)
    assert set(files) == {'README.md', 'MCP-PLAN.md', 'server.py', 'pyproject.toml',
                          '.env.example', 'client-config.example.json'}
    assert 'from mcp.server import MCPServer' in files['server.py']
    assert 'mcp.run(transport=transport)' in files['server.py']
    assert 'MCP_REMOTE_SECURITY_REVIEWED' in files['server.py']
    assert 'Windows 11' in files['README.md'] and 'macOS' in files['README.md']
    compile(files['server.py'], 'server.py', 'exec')


def test_mcp_project_requires_security_and_accepts_saved_state():
    state = {'mode': 'mcp', 'active': 'mcp', 'documents': {'mcp': {'fields': {}, 'content': '# MCP'}}}
    assert validate_document_state(state) == state
    with pytest.raises(ValueError):
        mcp_project_files({'title': 'MCP', 'content': '# MCP', 'fields': {'purpose': 'test'}})


@pytest.mark.parametrize('state', [{'mode': []}, {'documents': {'unknown': {}}}, {'mode': 'project', 'documents': {'core': {'fields': {'a': 5}}}}])
def test_rejects_malformed_state(state):
    with pytest.raises(ValueError):
        validate_document_state(state)
