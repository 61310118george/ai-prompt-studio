import io
import json
import stat
import os
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
    if os.name != "nt":  # Windows uses ACLs rather than POSIX permission bits.
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


def test_document_field_uses_only_confirmed_input(advisor):
    def fake(req, **kwargs):
        payload = json.loads(req.data)
        fields = json.loads(payload['contents'][0]['parts'][0]['text'])
        assert fields['document_type'] == 'core'
        assert fields['content'] == ''
        assert 'other_document' not in fields
        assert '不可捏造' in payload['systemInstruction']['parts'][0]['text']
        return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': '先確認需求。'}]}}]}).encode())
    advisor._open = fake
    result = advisor.draft_document_field({'consent': True, 'document_type': 'core', 'title': '測試',
                                          'goal': '先確認需求', 'other_document': 'PRIVATE'})
    assert result['original'] == '' and result['optimized'] == '先確認需求。'
    assert result['changed'] and '+先確認需求。' in result['diff']


@pytest.mark.parametrize('change', [{'consent': False}, {'goal': ''}, {'document_type': 'project'},
                                   {'audience': 'password: secret-value'}, {'content': 'a'*20001}])
def test_document_field_rejects_before_network(advisor, change):
    advisor._open = lambda *a, **kw: pytest.fail('Must not send')
    with pytest.raises(ValueError):
        advisor.draft_document_field({'consent': True, 'document_type': 'memory', 'title': 'test', 'goal': 'facts', **change})


def document_request(**changes):
    return {'consent': True, 'mode': 'revise', 'document_type': 'core', 'title': '測試',
            'field_id': 'purpose', 'content': '只整理需求', **changes}


def json_reply(value):
    return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(value, ensure_ascii=False)}]}}]}).encode())


def test_clarification_is_structured_and_scoped(advisor):
    def fake(req, **kwargs):
        payload = json.loads(req.data)
        data = json.loads(payload['contents'][0]['parts'][0]['text'])
        assert data['content'] == '只整理需求' and 'other_document' not in data
        return json_reply({'understanding': ['你希望整理需求。'], 'questions': ['是否僅整理，不執行？']})
    advisor._open = fake
    result = advisor.clarify_document(document_request(other_document='PRIVATE'))
    assert result['questions'] == ['是否僅整理，不執行？']


def test_writing_discards_unrequested_content(advisor):
    def fake(req, **kwargs):
        data = json.loads(json.loads(req.data)['contents'][0]['parts'][0]['text'])
        assert data['content'] == '' and data['field_id'] == ''
        return json_reply({'understanding': ['待確認方向'], 'questions': ['希望給誰看？']})
    advisor._open = fake
    advisor.clarify_document(document_request(mode='write'))


@pytest.mark.parametrize('changes', [{'consent': False}, {'content': ''}, {'mode': 'other'},
                                   {'field_id': 'background'}, {'title': ''}, {'content': 'password: secret-value'}])
def test_clarification_blocks_invalid_inputs(advisor, changes):
    advisor._open = lambda *a, **kw: pytest.fail('Must not send')
    with pytest.raises(ValueError):
        advisor.clarify_document(document_request(**changes))


@pytest.mark.parametrize('value', [[], {'understanding': [], 'questions': ['Q']},
                                 {'understanding': ['A'], 'questions': ['Q']*7},
                                 {'understanding': ['A'], 'questions': [3]}])
def test_clarification_rejects_bad_model_output(advisor, value):
    advisor._open = lambda *a, **kw: json_reply(value)
    with pytest.raises(ValueError):
        advisor.clarify_document(document_request())


def test_compose_uses_answers_and_limits_to_field(advisor):
    def fake(req, **kwargs):
        data = json.loads(json.loads(req.data)['contents'][0]['parts'][0]['text'])
        assert data['answers'] == ['不，需要先詢問']
        assert set(data['field_schema']) == {'purpose'}
        return json_reply({'fields': {'purpose': '先詢問需求，再整理。'}})
    advisor._open = fake
    request = document_request(clarification={'understanding': ['整理需求'], 'questions': ['直接執行？']}, answers=['不，需要先詢問'])
    assert advisor.compose_document(request)['fields'] == {'purpose': '先詢問需求，再整理。'}
    advisor._open = lambda *a, **kw: json_reply({'fields': {'rules': 'wrong target'}})
    with pytest.raises(ValueError):
        advisor.compose_document(request)


@pytest.mark.parametrize('kind', ['core', 'memory', 'skill'])
@pytest.mark.parametrize('field', ['role', 'task', 'ideas'])
def test_requirement_dimensions_revise_only_requested_field(advisor, kind, field):
    def fake(req, **kwargs):
        data = json.loads(json.loads(req.data)['contents'][0]['parts'][0]['text'])
        assert data['tags'] == '開發程式,開發程式/寫網頁'
        assert data['content'] == '希望能夠更好被搜尋找到'
        assert set(data['field_schema']) == {field}
        assert 'private_other_field' not in data
        return json_reply({'fields': {field: '希望改善網站的搜尋可見度。'}})
    advisor._open = fake
    result = advisor.compose_document(document_request(
        document_type=kind, field_id=field, tags='開發程式,開發程式/寫網頁',
        content='希望能夠更好被搜尋找到', private_other_field='DO NOT SEND',
        clarification={'understanding': ['搜尋可見度'], 'questions': ['是否指搜尋可見度？']}, answers=['是']))
    assert set(result['fields']) == {field}


@pytest.mark.parametrize('kind', ['core', 'memory', 'skill'])
def test_requirement_writing_returns_three_dimensions(advisor, kind):
    fields = {'role': '網站設計師', 'task': '設計網站', 'ideas': '注意搜尋可見度'}
    def fake(req, **kwargs):
        data = json.loads(json.loads(req.data)['contents'][0]['parts'][0]['text'])
        assert set(data['field_schema']) == set(fields)
        assert data['answers'] == list(fields.values())
        return json_reply({'fields': fields})
    advisor._open = fake
    result = advisor.compose_document(document_request(
        mode='write', document_type=kind,
        clarification={'understanding': ['網站需求'], 'questions': ['角色？', '任務？', '想法？']},
        answers=list(fields.values())))
    assert result['fields'] == fields


@pytest.mark.parametrize('answers', [[], [''], ['password: secret-value'], ['a'*2001]])
def test_compose_rejects_bad_answers_before_network(advisor, answers):
    advisor._open = lambda *a, **kw: pytest.fail('Must not send')
    with pytest.raises(ValueError):
        advisor.compose_document(document_request(clarification={'understanding': ['A'], 'questions': ['Q']}, answers=answers))


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
        assert payload['generationConfig']['maxOutputTokens']==480
        assert payload['generationConfig']['temperature']==0.2
        assert '回覆只能有' in payload['systemInstruction']['parts'][0]['text']
        assert '本機粗估提示詞輸入 Token：321' in payload['contents'][0]['parts'][0]['text']
        assert 'dummy-key' not in req.data.decode()
        return io.BytesIO(json.dumps({'candidates':[{'content':{'parts':[{'text':'hidden','thought':True},{'text':'<script>not executable</script>'}]},'finishReason':'MAX_TOKENS'}]}).encode())
    advisor._open=fake_open
    result=advisor.analyze({'content':'整理筆記','tool':'claude','consent':True,'estimated_tokens':321,'model_hint':'Sonnet 處理一般任務'})
    assert result['text']=='<script>not executable</script>' and result['truncated']


def test_optimize_uses_analysis_and_returns_reviewable_diff(advisor):
    original = '## 任務\n\n- 保留日期\n- 保留日期\n'
    optimized = '## 任務\n\n- 保留日期\n- 使用繁體中文'

    def fake_open(req, timeout):
        assert timeout == 45
        payload = json.loads(req.data)
        assert payload['generationConfig'] == {'maxOutputTokens': 8192, 'temperature': 0.15}
        assert '移除重複文字' in payload['systemInstruction']['parts'][0]['text']
        sent = payload['contents'][0]['parts'][0]['text']
        assert '<analysis>' in sent and original in sent
        return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': optimized}]}}]}).encode())

    advisor._open = fake_open
    result = advisor.optimize({'content': original, 'analysis': '建議移除重複條列。', 'tool': 'codex', 'consent': True})
    assert result['original'] == original
    assert result['optimized'] == optimized
    assert result['changed'] is True
    assert '--- 優化前' in result['diff'] and '+++ 優化後' in result['diff']
    assert '- 保留日期' in result['diff'] and '+- 使用繁體中文' in result['diff']


def test_section_optimization_sends_only_selected_fields(advisor):
    def fake_open(req, timeout):
        payload = json.loads(req.data)
        fields = json.loads(payload['contents'][0]['parts'][0]['text'])
        assert fields['title'] == '行銷文案'
        assert fields['tags'] == '寫作'
        assert fields['content'] == '請寫清楚'
        assert 'source' not in fields and 'path' not in fields
        assert '不要生成其他章節' in payload['systemInstruction']['parts'][0]['text']
        return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': '請以條列呈現重點。'}]}}]}).encode())
    advisor._open = fake_open
    result = advisor.optimize_section(dict(content='請寫清楚', title='行銷文案', tags='寫作',
        source='其他章節不應傳送', path='/private', consent=True))
    assert result['original'] == '請寫清楚' and result['changed']
    assert '+請以條列呈現重點。' in result['diff']


@pytest.mark.parametrize('overrides', [
    {'consent': False}, {'content': ''}, {'content': 'x' * 20001},
    {'tags': ['寫作']}, {'constraints': 'password: confidential'},
    {'title': 'AIza' + 'x' * 30}, {'audience': 'x' * 501},
])
def test_section_rejects_invalid_or_sensitive_context(advisor, overrides):
    advisor._open = lambda *a, **kw: pytest.fail('Must not send')
    with pytest.raises(ValueError):
        advisor.optimize_section(dict({'content': '整理文字', 'consent': True}, **overrides))


def test_optimize_requires_completed_analysis_and_rejects_truncation(advisor):
    with pytest.raises(ValueError, match='先完成'):
        advisor.optimize({'content': '請整理內容', 'analysis': '', 'tool': 'codex', 'consent': True})
    advisor._open = lambda *args, **kwargs: io.BytesIO(json.dumps({
        'candidates': [{'content': {'parts': [{'text': '不完整'}]}, 'finishReason': 'MAX_TOKENS'}]
    }).encode())
    with pytest.raises(ValueError, match='不完整內容'):
        advisor.optimize({'content': '請整理內容', 'analysis': '任務難度：低', 'tool': 'codex', 'consent': True})


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


@pytest.mark.parametrize('kind', ['core', 'memory', 'skill'])
def test_topic_specific_ai_schema_and_question_context(advisor, kind):
    from ai_memory_app.services.document_profiles import profile_fields
    spec = profile_fields(kind, '推廣行銷', '分析市場')
    request = document_request(mode='write', document_type=kind, schema_version=2,
                               major='推廣行銷', minor='分析市場')
    def clarify(req, **kwargs):
        data = json.loads(json.loads(req.data)['contents'][0]['parts'][0]['text'])
        assert data['field_spec'] == spec
        assert '同業資料' in str(data['field_spec'])
        return json_reply({'understanding':['研究市場'], 'questions':['研究哪個地區？']})
    advisor._open = clarify
    review = advisor.clarify_document(request)
    def compose(req, **kwargs):
        data = json.loads(json.loads(req.data)['contents'][0]['parts'][0]['text'])
        assert set(data['field_schema']) == {f['id'] for f in spec}
        return json_reply({'fields':{f['id']:'使用者已確認資料' for f in spec}})
    advisor._open = compose
    assert len(advisor.compose_document({**request,'clarification':review,'answers':['台北']})['fields']) == len(spec)
