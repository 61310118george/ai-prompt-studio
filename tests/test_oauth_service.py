import hashlib
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient


spec = importlib.util.spec_from_file_location('oauth_broker', Path(__file__).resolve().parents[1] / 'oauth-service/app.py')
broker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(broker)
CONFIG = {'PUBLIC_BASE_URL':'https://broker.example.com', 'BROKER_KEY':'test-key-'*5, 'META_GRAPH_VERSION':'v26.0', 'META_APP_ID':'123', 'META_APP_SECRET':'test-only', 'THREADS_APP_ID':'456', 'THREADS_APP_SECRET':'test-only', 'ALLOWED_FACEBOOK_IDS':'1', 'ALLOWED_THREADS_IDS':'2'}
HEADERS = {'Authorization':'Bearer ' + CONFIG['BROKER_KEY']}
VERIFIER = 'a'*43


class Meta:
    def authorization_url(self, provider, state):
        return 'https://threads.net/oauth/authorize?state=' + state
    def exchange(self, provider, code):
        if code == 'error': raise ValueError('secret-token-must-not-leak')
        return [{'platform':'threads','account_id':'2','name':'Test','access_token':'private-token'}]


def start(client):
    response = client.post('/auth/start', headers=HEADERS, json={'provider':'threads','challenge':hashlib.sha256(VERIFIER.encode()).hexdigest()})
    assert response.status_code == 200
    data = response.json()
    return data['session_id'], parse_qs(urlsplit(data['authorization_url']).query)['state'][0]


def test_authorization_claim_binding_and_replay():
    client = TestClient(broker.create_app(CONFIG, Meta()))
    session, state = start(client)
    body = {'session_id':session,'verifier':VERIFIER}
    assert client.post('/auth/claim', json=body).status_code == 401
    assert client.post('/auth/claim', headers=HEADERS,json={**body,'verifier':'b'*43}).status_code == 400
    assert client.post('/auth/claim', headers=HEADERS,json=body).json()['status'] == 'pending'
    assert client.get('/auth/callback/threads?code=ok&state=wrong').status_code == 400
    response = client.get('/auth/callback/threads',params={'state':state,'code':'ok'})
    assert 'private-token' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert client.get('/auth/callback/threads',params={'state':state,'code':'ok'}).status_code == 400
    response = client.post('/auth/claim',headers=HEADERS,json=body)
    assert response.json()['accounts'][0]['access_token'] == 'private-token'
    assert client.post('/auth/claim',headers=HEADERS,json=body).status_code == 400


def test_decline_error_and_expiry(monkeypatch):
    client = TestClient(broker.create_app(CONFIG, Meta()))
    for params in ({'error':'access_denied'}, {'code':'error'}):
        session,state = start(client)
        response = client.get('/auth/callback/threads',params={**params,'state':state})
        assert 'secret-token' not in response.text
        assert client.post('/auth/claim',headers=HEADERS,json={'session_id':session,'verifier':VERIFIER}).json() == {'status':'error'}
    session,state = start(client)
    now=broker.time.monotonic()
    monkeypatch.setattr(broker.time,'monotonic',lambda:now+601)
    assert client.get('/auth/callback/threads',params={'state':state,'code':'ok'}).status_code == 400


def test_authlib_generated_login_urls_are_read_only():
    meta = broker.Meta(CONFIG)
    for provider in ('facebook','threads'):
        url = meta.authorization_url(provider,'state')
        query = parse_qs(urlsplit(url).query)
        assert query['state'] == ['state']
        assert query['redirect_uri'] == [CONFIG['PUBLIC_BASE_URL']+'/auth/callback/'+provider]
        assert 'publish' not in query['scope'][0]
