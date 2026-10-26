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
    assert api.unlock_developer_mode('61310118')['data']['enabled']


def test_fixed_password_restart_and_lock(api):
    assert api.get_developer_status()['data'] == dict(enabled=False, retry_after=0)
    assert not hasattr(api, 'setup_developer_password')
    assert not hasattr(api, 'change_developer_password')
    # An existing installation's old password must no longer control access.
    with connect(api.repository.db_path) as db:
        db.execute("INSERT INTO settings(key,value,updated_at) VALUES('developer_mode_password',?, '')", (json.dumps({'digest':'old-value'}),))
    setup(api)
    with connect(api.repository.db_path) as db:
        stored = db.execute("SELECT value FROM settings WHERE key='developer_mode_attempts'").fetchone()[0]
    assert '61310118' not in stored
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
    assert not fresh.unlock_developer_mode('61310118')['ok']


def test_locked_inflight_result_is_discarded(api):
    setup(api)
    def result_after_lock():
        api.lock_developer_mode()
        return {'private': 'result'}
    result = api._developer_call(result_after_lock)
    assert not result['ok']
    assert 'private' not in str(result)
