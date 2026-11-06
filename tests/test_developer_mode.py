import json

import pytest

from ai_memory_app.data.database import connect, initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.desktop_api import DesktopApi, LOCAL_PROMPT_SCOPE


@pytest.fixture
def api(tmp_path):
    db = tmp_path / 'app.sqlite3'
    initialize_database(db)
    return DesktopApi(MemoryRepository(db))


def setup(api):
    assert api.unlock_developer_mode('5830485')['data']['enabled']


def mcp_state():
    return {'mode': 'mcp', 'active': 'mcp', 'documents': {'mcp': {'fields': {}, 'content': '# MCP'}}}


def mcp_project():
    return {'title': 'MCP', 'content': '# MCP', 'fields': {
        'purpose': 'test', 'tools': 'test', 'connection': 'stdio',
        'security': 'confirm', 'verification': 'inspect'}}


def test_fixed_password_restart_and_lock(api):
    assert api.get_developer_status()['data'] == dict(enabled=False, retry_after=0)
    assert not hasattr(api, 'setup_developer_password')
    assert not hasattr(api, 'change_developer_password')
    # An existing installation's old password must no longer control access.
    with connect(api.repository.db_path) as db:
        db.execute("INSERT INTO settings(key,value,updated_at) VALUES('developer_mode_password',?, '')", (json.dumps({'digest':'old-value'}),))
    assert not api.unlock_developer_mode('61310118')['ok']
    assert not api.get_developer_status()['data']['enabled']
    setup(api)
    with connect(api.repository.db_path) as db:
        stored = db.execute("SELECT value FROM settings WHERE key='developer_mode_attempts'").fetchone()[0]
    assert '5830485' not in stored
    fresh = DesktopApi(MemoryRepository(api.repository.db_path))
    assert not fresh.get_developer_status()['data']['enabled']
    assert not fresh.unlock_developer_mode('incorrect-password')['ok']
    assert api.lock_developer_mode()['data']['enabled'] is False
    assert api.list_prompts(LOCAL_PROMPT_SCOPE)['ok']
    assert api.get_prompt_tag_catalog()['ok']
    assert api.get_cloud_settings()['ok']


@pytest.mark.parametrize('method,args', [
    ('get_social_settings', ()), ('configure_social', ('https://example.com', 'code')),
    ('begin_social_login', ('facebook',)), ('poll_social_login', ()),
    ('select_social_accounts', ([],)), ('disconnect_social', ('threads',)),
    ('clear_social_data', ('threads',)), ('sync_social', ('threads',)),
    ('list_social_posts', ('threads',)), ('preview_marketing', ('prompt', [1])),
    ('optimize_marketing', ('preview', True)), ('apply_marketing', (1, 'prompt', [1])),
    ('run_memory_health_check', ('/not-authorized', 'codex')),
    ('analyze_with_ai', ({'content': 'test', 'consent': True},)),
    ('optimize_with_ai', ({'content': 'test', 'consent': True},)),
    ('preview_mcp_project', (mcp_project(),)),
    ('export_mcp_project', (mcp_project(),)),
    ('clarify_document', ({'document_type': 'mcp'},)),
    ('compose_document', ({'document_type': 'mcp'},)),
    ('draft_document_field', ({'document_type': 'mcp'},)),
    ('save_prompt_draft', ({'project_path': LOCAL_PROMPT_SCOPE, 'document_state': mcp_state()},)),
    ('save_prompt', ({'project_path': LOCAL_PROMPT_SCOPE, 'document_state': mcp_state()},)),
])
def test_backend_blocks_locked_features(api, method, args):
    for configured in (False, True):
        if configured:
            setup(api)
            api.lock_developer_mode()
        response = getattr(api, method)(*args)
        assert not response['ok']
        assert '開發人員' in response['error']


def test_cooldown_persists(api):
    setup(api)
    api.lock_developer_mode()
    for _ in range(5):
        assert not api.unlock_developer_mode('incorrect-password')['ok']
    fresh = DesktopApi(MemoryRepository(api.repository.db_path))
    assert fresh.get_developer_status()['data']['retry_after'] > 0
    assert not fresh.unlock_developer_mode('5830485')['ok']


def test_locked_inflight_result_is_discarded(api):
    setup(api)
    def result_after_lock():
        api.lock_developer_mode()
        return {'private': 'result'}
    result = api._developer_call(result_after_lock)
    assert not result['ok']
    assert 'private' not in str(result)


def test_mcp_saved_content_is_hidden_again_after_lock(api):
    setup(api)
    request = {'project_path': LOCAL_PROMPT_SCOPE, 'title': 'MCP 私有草稿', 'category': '一般',
               'tags': '', 'content': '# MCP', 'tool': 'codex', 'document_state': mcp_state()}
    saved = api.save_prompt(request)['data']
    assert api.save_prompt_draft(request)['ok']
    assert any(item['id'] == saved['id'] for item in api.list_prompts(LOCAL_PROMPT_SCOPE)['data'])
    assert api.load_prompt_draft(LOCAL_PROMPT_SCOPE)['data']['document_state']['mode'] == 'mcp'
    api.lock_developer_mode()
    assert all(item['id'] != saved['id'] for item in api.list_prompts(LOCAL_PROMPT_SCOPE)['data'])
    assert api.load_prompt_draft(LOCAL_PROMPT_SCOPE)['data'] is None
    versions = api.list_prompt_versions(LOCAL_PROMPT_SCOPE, saved['id'])
    assert not versions['ok'] and '開發人員' in versions['error']
