import json
from pathlib import Path

import pytest

from ai_memory_app.data.database import initialize_database
from ai_memory_app.data.prompt_library import PromptLibrary
from ai_memory_app.services.document_project import project_files, skill_name, validate_document_state, write_project


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


@pytest.mark.parametrize('state', [{'mode': []}, {'documents': {'unknown': {}}}, {'mode': 'project', 'documents': {'core': {'fields': {'a': 5}}}}])
def test_rejects_malformed_state(state):
    with pytest.raises(ValueError):
        validate_document_state(state)
