import io
import json
import time
from datetime import datetime, timezone

import pytest

from ai_memory_app.data.database import connect, initialize_database
from ai_memory_app.data.repository import MemoryRepository
from ai_memory_app.services.social_data import SocialData, SocialError
from ai_memory_app.services.desktop_api import DesktopApi
from ai_memory_app.services.cloud_advisor import CloudAdvisor


class Secrets:
    def __init__(self): self.values = {}
    def get(self, key): return self.values.get(key, '')
    def set(self, key, value): self.values[key] = value
    def delete(self, key): self.values.pop(key, None)


@pytest.fixture
def social(tmp_path):
    db = tmp_path / 'social.db'
    initialize_database(db)
    service = SocialData(db, credentials=Secrets())
    service._candidates = (time.monotonic(), [{'platform': 'threads', 'account_id': '1', 'name': 'Company', 'access_token': 'secret'}])
    service.select_accounts(['0'])
    return service


def transport(url, token, params=None, payload=None):
    assert token == 'secret'
    if url.endswith('/threads'):
        if params.get('after'):
            return {'data': [{'id': '2', 'text': 'Second', 'timestamp': datetime.now(timezone.utc).isoformat(), 'media_type': 'TEXT'}]}
        return {'data': [{'id': '1', 'text': 'First', 'timestamp': datetime.now(timezone.utc).isoformat(), 'media_type': 'TEXT'}], 'paging': {'next': 'https://untrusted.invalid/ignored', 'cursors': {'after': 'page2'}}}
    if '/insights' in url:
        return {'data': [{'name': 'views', 'values': [{'value': 20}]}, {'name': 'likes', 'values': [{'value': 3}]}]}
    raise AssertionError(url)


def test_pagination_snapshots_and_immutable_evidence(social):
    social.request = transport
    assert social.sync('threads')['count'] == 2
    posts = social.posts('threads')
    assert len(posts) == 2
    assert posts[0]['metrics']['shares'] is None
    ids = [p['snapshot_id'] for p in posts]
    social.sync('threads')
    assert len(social.posts('threads')) == 2
    with connect(social.db_path) as db:
        db.execute("UPDATE social_posts SET content='Changed'")
        assert db.execute('SELECT COUNT(*) FROM social_snapshots').fetchone()[0] == 4
    assert {e['content'] for e in social.evidence(ids)} == {'First', 'Second'}
    assert 'secret' not in json.dumps(social.settings())
    social.disconnect('threads')
    assert not social.secrets.get('threads:1')
    assert len(social.posts('threads')) == 2
    social.clear('threads')
    assert social.posts('threads') == []


def test_partial_metrics_and_rate_limit_no_partial_commit(social):
    def partial(url, token, params=None, payload=None):
        if url.endswith('insights'):
            if params['metric'] != 'likes': raise SocialError('unavailable', 'unsupported')
            return {'data': [{'name':'likes', 'values':[{'value': 5}]}]}
        return transport(url, token, params, payload)
    social.request = partial
    assert social.sync('threads')['warnings']
    assert social.posts('threads')[0]['metrics']['likes'] == 5
    assert social.posts('threads')[0]['metrics']['views'] is None
    def rate(*args, **kwargs): raise SocialError('slow down', 'rate_limited')
    social.request = rate
    with pytest.raises(SocialError): social.sync('threads')
    assert len(social.posts('threads')) == 2
    assert social.settings()['accounts'][0]['status'] == 'rate_limited'


def test_limit_and_expired_credentials(social):
    def many(url, token, params=None, payload=None):
        if url.endswith('/threads'):
            return {'data': [{'id': str(i), 'timestamp': datetime.now(timezone.utc).isoformat(), 'text': 'post'} for i in range(150)]}
        return {'data': []}
    social.request = many
    assert social.sync('threads')['limited']
    assert len(social.posts('threads')) == 100
    with connect(social.db_path) as db: db.execute('UPDATE social_accounts SET expires_at=1')
    with pytest.raises(SocialError, match='過期'): social.sync('threads')


def test_login_hides_tokens_and_consumes_selection(social, monkeypatch):
    monkeypatch.setattr('ai_memory_app.services.social_data.webbrowser.open', lambda url: True)
    social.configure('https://broker.example.com', 'x'*40)
    def broker(url, token, params=None, payload=None):
        if url.endswith('/start'): return {'session_id':'session', 'authorization_url':'https://threads.net/oauth/authorize'}
        return {'status':'ready','accounts':[{'platform':'threads','account_id':'2','name':'New','access_token':'private'}]}
    social.request = broker
    social.begin('threads')
    assert 'private' not in json.dumps(social.poll())
    social.select_accounts(['0'])
    assert social.secrets.get('threads:2') == 'private'
    assert not social.secrets.get('threads:1')
    with pytest.raises(ValueError): social.select_accounts(['0'])


def test_marketing_evidence_diff_and_stale_apply(social):
    social.request = transport
    social.sync('threads')
    api = DesktopApi(MemoryRepository(social.db_path))
    api.unlock_developer_mode('61310118')
    api._social = social
    class Credential:
        def load(self): return 'fake-key'
    api._cloud_advisor = CloudAdvisor(Credential())
    ids = [social.posts('threads')[0]['snapshot_id']]
    generated = {'observations':[{'text':'樣本不足', 'snapshot_ids':ids}], 'suggestions':[{'text':'先測試開頭', 'snapshot_ids':ids}], 'optimized':'新的提示詞'}
    api._cloud_advisor._open = lambda *a, **k: io.BytesIO(json.dumps({'candidates':[{'content':{'parts':[{'text':json.dumps(generated)}]}}]}).encode())
    preview = api.preview_marketing('原始提示詞', ids)['data']
    result = api.optimize_marketing(preview['preview_id'], True)['data']
    assert result['diff'] and result['evidence'][0]['snapshot_id'] == ids[0]
    assert api.apply_marketing(result['run_id'], '原始提示詞', ids)['ok']
    assert not api.apply_marketing(result['run_id'], '已修改', ids)['ok']
    social.sync('threads')
    assert not api.apply_marketing(result['run_id'], '原始提示詞', ids)['ok']
    generated['observations'][0]['snapshot_ids'] = [99999]
    preview = api.preview_marketing('原始提示詞', ids)['data']
    assert not api.optimize_marketing(preview['preview_id'], True)['ok']


@pytest.mark.parametrize('url', ['http://broker.example.com','https://user:pass@broker.example.com','https://broker.example.com/path'])
def test_broker_origin_validation(social, url):
    with pytest.raises(ValueError): social.configure(url, 'x'*40)


@pytest.mark.parametrize('platform,edge', [('facebook','posts'), ('instagram','media')])
def test_facebook_and_instagram_adapters(social, platform, edge):
    with connect(social.db_path) as db:
        db.execute("INSERT INTO social_config VALUES('graph_version','v26.0')")
    social._candidates = (time.monotonic(), [{'platform':platform,'account_id':'3','name':'Company','access_token':'secret'}])
    social.select_accounts(['0'])
    def graph(url, token, params=None, payload=None):
        assert url.startswith('https://graph.facebook.com/v26.0/') and token == 'secret'
        if url.endswith('/'+edge):
            post={'id':'55','timestamp':datetime.now(timezone.utc).isoformat(),'caption':'IG caption','media_type':'IMAGE','like_count':7,'comments_count':2}
            if platform == 'facebook':
                post={'id':'3_55','created_time':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+0000'),'message':'FB post','reactions':{'summary':{'total_count':9}},'comments':{'summary':{'total_count':3}},'shares':{'count':1}}
            return {'data':[post]}
        return {'data':[{'name':'post_media_view' if platform=='facebook' else 'views','values':[{'value':42}]}]}
    social.request=graph
    assert social.sync(platform)['count']==1
    post=social.posts(platform)[0]
    assert post['content']==('FB post' if platform=='facebook' else 'IG caption')
    assert post['metrics']['reactions' if platform=='facebook' else 'likes']==(9 if platform=='facebook' else 7)
    assert post['metrics']['post_media_view' if platform=='facebook' else 'views']==42


def test_marketing_requires_consent_and_rejects_secrets(social):
    class Credential:
        def load(self): return 'fake-key'
    advisor=CloudAdvisor(Credential())
    advisor._open=lambda *a,**k: (_ for _ in ()).throw(AssertionError('No request expected'))
    with pytest.raises(ValueError,match='確認'):
        advisor.marketing('草稿',[],False)
    with pytest.raises(ValueError,match='金鑰'):
        advisor.marketing('草稿',[{'content':'AIza'+'a'*35}],True)
