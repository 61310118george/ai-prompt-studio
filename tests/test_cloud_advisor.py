import io
import json
import stat
import urllib.error

import pytest

from ai_memory_app.services.cloud_advisor import CloudAdvisor, NoRedirect
from ai_memory_app.services.credential_store import LocalCredentialStore


class MemoryCredentialStore:
    def __init__(self):
        self.value = ''

    def load(self):
        return self.value

    def save(self, secret):
        self.value = secret

    def clear(self):
        self.value = ''


def test_local_credential_store_is_private_and_removable(tmp_path):
    store = LocalCredentialStore(tmp_path / "app-support" / "credentials.json")
    store.save("AQ." + "a" * 35)
    assert store.load().startswith("AQ.")
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    store.clear()
    assert store.load() == ""


@pytest.fixture
def advisor():
    service=CloudAdvisor(MemoryCredentialStore())
    service._open=lambda *a,**kw:io.BytesIO(b'{"name":"models/gemini-3.5-flash-lite"}')
    service.configure({'api_key':'AQ.'+'a'*35,'model':'gemini-3.5-flash-lite'})
    return service


def test_local_credential_configuration(advisor):
    assert advisor.status()['configured']
    assert advisor.status()['connection']=='connected'
    assert 'dummy' not in json.dumps(advisor.status())
    assert not CloudAdvisor(MemoryCredentialStore()).status()['configured']
    advisor.configure({'clear':True})
    assert not advisor.status()['configured']
    assert advisor.status()['connection']=='unconfigured'


@pytest.mark.parametrize('payload',[
    {'content':'abc','tool':'codex'},
    {'content':'a'*20001,'tool':'codex','consent':True},
    {'content':'password: confidential','tool':'codex','consent':True},
    {'content':'abc','tool':'local','consent':True},
    {'content':'AIza'+'a'*30,'tool':'codex','consent':True},
])
def test_rejects_before_network(advisor,payload):
    advisor._open=lambda *a,**kw:pytest.fail('Must not send')
    with pytest.raises(ValueError):advisor.analyze(payload)


def test_minimal_payload_and_literal_response(advisor):
    def fake_open(req,timeout):
        assert timeout==35
        assert req.full_url=='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'
        payload=json.loads(req.data)
        assert set(payload)=={'systemInstruction','contents','generationConfig'}
        assert payload['generationConfig']['maxOutputTokens']==1600
        assert 'dummy-key' not in req.data.decode()
        return io.BytesIO(json.dumps({'candidates':[{'content':{'parts':[{'text':'hidden','thought':True},{'text':'<script>not executable</script>'}]},'finishReason':'MAX_TOKENS'}]}).encode())
    advisor._open=fake_open
    result=advisor.analyze({'content':'整理筆記','tool':'claude','consent':True})
    assert result['text']=='<script>not executable</script>' and result['truncated']


@pytest.mark.parametrize('code',[400,401,403,404,429,500,503,302])
def test_errors_do_not_echo_provider_or_key(advisor,code):
    def fail(*a,**kw):
        raise urllib.error.HTTPError('https://example.invalid',code,'dummy-key-not-real-12345',{},None)
    advisor._open=fail
    with pytest.raises(ValueError) as error:advisor.analyze({'content':'test','consent':True})
    assert 'dummy-key' not in str(error.value)
    assert str(code) in str(error.value)
    assert advisor._lock.acquire(blocking=False)
    advisor._lock.release()
    assert advisor.status()['connection']=='error'


def test_timeout_and_bad_response(advisor):
    def fail(*a,**kw):raise TimeoutError()
    advisor._open=fail
    with pytest.raises(ValueError,match='逾時'):advisor.analyze({'content':'test','consent':True})
    advisor._open=lambda *a,**kw:io.BytesIO(b'not json')
    with pytest.raises(ValueError,match='格式'):advisor.analyze({'content':'test','consent':True})
    advisor._open=lambda *a,**kw:io.BytesIO(b'{}')
    with pytest.raises(ValueError,match='未提供'):advisor.analyze({'content':'test','consent':True})


def test_reject_redirect_and_invalid_model(advisor):
    assert NoRedirect().redirect_request(None,None,302,'',{},'http://malicious.invalid') is None
    with pytest.raises(ValueError):advisor.configure({'api_key':'AQ.'+'a'*35,'model':'../malicious'})
    advisor._lock.acquire()
    try:
        with pytest.raises(ValueError,match='進行中'):advisor.analyze({'content':'test','consent':True})
    finally:advisor._lock.release()


def test_configure_verifies_connection_without_submitting_content():
    service=CloudAdvisor(MemoryCredentialStore())
    def failed_probe(req, timeout):
        assert req.method=='POST' and req.data
        assert req.full_url.endswith('/models/gemini-3.5-flash-lite:generateContent')
        raise urllib.error.HTTPError(req.full_url, 401, 'invalid', {}, None)
    service._open=failed_probe
    status=service.configure({'api_key':'AQ.'+'a'*35,'model':'gemini-3.5-flash-lite'})
    assert status['configured'] and status['connection']=='error'
    assert 'API Key 無效' in status['connection_message']


def test_saved_store_is_reused_and_probe_must_succeed():
    store=MemoryCredentialStore()
    service=CloudAdvisor(store)
    service._open=lambda *args,**kwargs:io.BytesIO(b'{"candidates":[{"content":{"parts":[{"text":"OK"}]}}]}')
    status=service.configure({'api_key':'AQ.'+'a'*35,'model':'models/gemini-3.5-flash-lite'})
    assert status['connection']=='connected' and status['key_saved'] and store.value.startswith('AQ.')
    restored=CloudAdvisor(store)
    assert restored.status()['connection']=='unverified'
    restored._open=service._open
    assert restored.configure({'api_key':'','model':'gemini-3.5-flash-lite'})['connection']=='connected'
