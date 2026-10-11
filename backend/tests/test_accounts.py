"""Exercise the real account boundary with an offline provider, never a bypass."""

import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.accounts.provider import SupabaseBackend
from backend.app.accounts.routes import ACCESS_COOKIE, REFRESH_COOKIE
from backend.app.accounts.storage import cipher
from backend.app.main import create_app
from backend.tests.account_helpers import FakeSupabase
from backend.tests.test_api import multipart


@pytest.fixture
def provider():
    return FakeSupabase()


@pytest.mark.parametrize('method,path', [
    ('GET', '/api/report'), ('GET', '/api/affordability?amount=1'),
    ('GET', '/api/report/narrative'), ('POST', '/api/ask'),
    ('POST', '/api/upload'), ('POST', '/api/reset'),
    ('POST', '/api/import'), ('GET', '/api/import/sources'), ('POST', '/api/import/clear'),
    ('GET', '/api/plaid/status'), ('POST', '/api/plaid/link-token'),
    ('POST', '/api/plaid/exchange'), ('POST', '/api/plaid/sandbox'), ('POST', '/api/plaid/refresh'),
    ('GET', '/api/auth/me'), ('POST', '/api/auth/password'), ('POST', '/api/companies'),
])
def test_anonymous_private_requests_fail_before_providers(provider, method, path):
    with TestClient(create_app(auth_backend=provider)) as client:
        body = {'name': 'test'} if path == '/api/companies' else {'password': 'long-passphrase-123'}
        assert client.request(method, path, json=body).status_code == 401
    assert provider.calls == []


def login(client, email='owner@example.com', password='long-passphrase-123'):
    return client.post('/api/auth/login', json={'email': email, 'password': password})


def test_signup_confirmation_and_password_validation(provider):
    provider.confirm_email = True
    with TestClient(create_app(auth_backend=provider)) as client:
        assert client.post('/api/auth/signup', json={'email': 'bad', 'password': 'short'}).status_code == 422
        response = client.post('/api/auth/signup', json={'email': 'owner@example.com', 'password': 'long-passphrase-123'})
        assert response.status_code == 200
        assert response.json()['signed_in'] is False
        assert ACCESS_COOKIE not in client.cookies
        assert 'password' not in response.json()


def test_login_refresh_logout_and_secure_cookie_contract(provider, monkeypatch):
    provider.add_user('owner@example.com', 'long-passphrase-123')
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    with TestClient(create_app(auth_backend=provider), base_url='https://testserver') as client:
        assert login(client, password='incorrect').status_code == 401
        response = login(client)
        assert response.status_code == 200
        assert set(response.json()) == {'user'}
        for cookie in response.headers.get_list('set-cookie'):
            assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=lax' in cookie
            assert 'Path=/api' in cookie
        old = client.cookies.get(ACCESS_COOKIE)
        assert client.get('/api/auth/me').status_code == 200
        assert client.post('/api/auth/refresh').status_code == 200
        assert client.cookies.get(ACCESS_COOKIE) != old
        assert client.post('/api/auth/logout').status_code == 200
        assert ACCESS_COOKIE not in client.cookies and REFRESH_COOKIE not in client.cookies
        assert client.get('/api/auth/me').status_code == 401
        assert client.post('/api/auth/refresh').status_code == 401


def test_recovery_callback_checks_both_tokens_and_changes_password(provider):
    session = provider.add_user('owner@example.com', 'long-passphrase-123')
    other = provider.add_user()
    with TestClient(create_app(auth_backend=provider)) as client:
        assert client.post('/api/auth/recover', json={'email': 'unknown@example.com'}).json()['message'].startswith('If an account exists')
        mixed = {'access_token': session['access_token'], 'refresh_token': other['refresh_token']}
        assert client.post('/api/auth/session', json=mixed).status_code == 401
        assert ACCESS_COOKIE not in client.cookies
        pair = {k: session[k] for k in ('access_token', 'refresh_token')}
        assert client.post('/api/auth/session', json=pair).status_code == 200
        assert client.post('/api/auth/password', json={'password': 'new-passphrase-123'}).status_code == 200
        client.post('/api/auth/logout')
        assert login(client, password='new-passphrase-123').status_code == 200


def test_company_ownership_cannot_be_changed_by_header_or_old_cookie(provider):
    first, second = provider.add_user(), provider.add_user()
    own = provider.company(first['user']['id'], seed=True)
    foreign = provider.company(second['user']['id'], seed=True)
    with TestClient(create_app(auth_backend=provider), headers={'Authorization': f"Bearer {first['access_token']}"}) as client:
        assert [c['id'] for c in client.get('/api/auth/me').json()['companies']] == [own['id']]
        assert client.get('/api/report').status_code == 409
        client.cookies.set('toolbelt_session', foreign['id'])
        assert client.get('/api/report', headers={'X-Company-ID': foreign['id']}).status_code == 404
        assert client.post('/api/reset', headers={'X-Company-ID': foreign['id']}).status_code == 404
        assert client.get('/api/report', headers={'X-Company-ID': own['id']}).status_code == 200
        assert client.get('/api/report', headers={'Authorization': 'Bearer invalid', 'X-Company-ID': own['id']}).status_code == 401


def test_empty_company_upload_persists_across_restart_and_other_browser(provider, sample_files):
    session = provider.add_user('owner@example.com', 'long-passphrase-123')
    company = provider.company(session['user']['id'])
    headers = {'X-Company-ID': company['id']}
    with TestClient(create_app(auth_backend=provider)) as client:
        login(client).raise_for_status()
        assert client.get('/api/report', headers=headers).json()['has_books'] is False
        assert client.post('/api/ask', json={'question': 'My expenses?'}, headers=headers).status_code == 409
        uploaded = client.post('/api/upload', files=multipart(sample_files), headers=headers)
        uploaded.raise_for_status()
        assert uploaded.json()['monthly_summary']['expenses'] == 52900
        saved = json.loads(cipher().decrypt(provider.states[company['id']]['payload'].encode()))
        assert json.loads(saved['books']['business.json']) == json.loads(sample_files['business.json'])
        assert 'Ridgeline' not in provider.states[company['id']]['payload']
        before = dict(provider.states[company['id']])
        invalid = sample_files | {'invoices.csv': 'invoice_id\n'}
        assert client.post('/api/upload', files=multipart(invalid), headers=headers).status_code == 422
        assert provider.states[company['id']] == before
        client.post('/api/auth/logout').raise_for_status()
    # New ASGI application and cookie jar; only database state is retained.
    with TestClient(create_app(auth_backend=provider)) as restarted:
        login(restarted).raise_for_status()
        report = restarted.get('/api/report', headers=headers).json()
        assert report['monthly_summary']['expenses'] == 52900
        assert report['is_sample'] is False
        restarted.post('/api/reset', headers=headers).raise_for_status()
        assert restarted.get('/api/report', headers=headers).json()['has_books'] is False
        assert restarted.get('/api/demo/report').json()['monthly_summary']['expenses'] == 52900


def test_new_companies_belong_to_authenticated_user_and_start_empty(provider):
    session = provider.add_user()
    with TestClient(create_app(auth_backend=provider), headers={'Authorization': f"Bearer {session['access_token']}"}) as client:
        assert client.post('/api/companies', json={'name': '   '}).status_code == 422
        response = client.post('/api/companies', json={'name': ' New business ', 'owner_id': 'someone-else'})
        response.raise_for_status()
        company = response.json()['company']
        assert provider.company_rows[company['id']]['owner_id'] == session['user']['id']
        assert company['name'] == 'New business'
        assert client.get('/api/report', headers={'X-Company-ID': company['id']}).json()['has_books'] is False


def test_foreign_origin_cannot_login_or_mutate_company(provider, monkeypatch):
    monkeypatch.setenv('PUBLIC_APP_URL', 'https://app.example.com')
    session = provider.add_user()
    company = provider.company(session['user']['id'], seed=True)
    with TestClient(create_app(auth_backend=provider), headers={'Authorization': f"Bearer {session['access_token']}", 'X-Company-ID': company['id']}) as client:
        assert client.post('/api/reset', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/auth/logout', headers={'Origin': 'https://evil.example'}).status_code == 403
        assert client.post('/api/reset', headers={'Origin': 'https://app.example.com'}).status_code == 200


def test_missing_encryption_key_blocks_bank_calls_early(provider, monkeypatch):
    session = provider.add_user()
    company = provider.company(session['user']['id'])
    monkeypatch.delenv('APP_DATA_KEY')
    with TestClient(create_app(auth_backend=provider), headers={'Authorization': f"Bearer {session['access_token']}", 'X-Company-ID': company['id']}) as client:
        response = client.post('/api/plaid/exchange', json={'public_token': 'unused'})
        assert response.status_code == 503 and 'encryption' in response.json()['detail']
        assert not provider.states


def test_storage_conflict_does_not_claim_upload_success(provider, sample_files, monkeypatch):
    session = provider.add_user()
    company = provider.company(session['user']['id'], seed=True)
    original = dict(provider.states[company['id']])
    def conflict(*args):
        raise HTTPException(409, 'Records changed in another request.')
    monkeypatch.setattr(provider, 'save', conflict)
    with TestClient(create_app(auth_backend=provider), headers={'Authorization': f"Bearer {session['access_token']}", 'X-Company-ID': company['id']}) as client:
        assert client.post('/api/upload', files=multipart(sample_files)).status_code == 409
        assert provider.states[company['id']] == original


def test_provider_uses_user_jwt_for_rls_and_sanitizes_errors(monkeypatch):
    monkeypatch.setenv('SUPABASE_URL', 'https://project.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_test')
    def handler(request):
        assert request.headers['apikey'] == 'sb_publishable_test'
        assert request.headers['authorization'] == 'Bearer user-token'
        if request.method == 'PATCH':
            assert request.url.params['revision'] == 'eq.previous'
            return httpx.Response(200, json=[])
        if request.url.path.endswith('companies'):
            return httpx.Response(200, json=[])
        return httpx.Response(401, json={'message': 'sensitive diagnostic'})
    provider = SupabaseBackend(transport=httpx.MockTransport(handler))
    assert provider.companies('user-token') == []
    with pytest.raises(HTTPException) as error:
        provider.verify('user-token')
    assert error.value.status_code == 401 and 'sensitive' not in error.value.detail
    with pytest.raises(HTTPException) as error:
        provider.save('user-token', 'company', 'previous', 'new', 'ciphertext')
    assert error.value.status_code == 409


def test_plaid_tokens_are_encrypted_and_survive_restart_without_cross_company_access(provider, monkeypatch):
    from backend.app.integrations import plaid, routes
    from backend.tests.test_integrations import PLAID_TX, ACCOUNTS
    session = provider.add_user()
    company = provider.company(session['user']['id'])
    second = provider.company(session['user']['id'])
    headers = {'Authorization': f"Bearer {session['access_token']}", 'X-Company-ID': company['id']}
    owners, used_tokens = [], []
    class Bank:
        async def close(self): pass
        async def link_token(self, owner):
            owners.append(owner)
            return 'short-lived-link-token'
        async def exchange(self, public):
            return 'private-bank-access-token', 'bank-item'
        async def sync(self, access):
            used_tokens.append(access)
            return PLAID_TX, ACCOUNTS, True
    async def categorize(transactions, **kwargs):
        for tx in transactions:
            tx.category = 'income' if tx.amount > 0 else 'materials'
    monkeypatch.setattr(plaid, 'PlaidClient', Bank)
    monkeypatch.setattr(routes, 'categorize', categorize)
    monkeypatch.setattr(routes, 'agent_status', lambda: {'available': True})
    with TestClient(create_app(auth_backend=provider), headers=headers) as client:
        assert client.post('/api/plaid/link-token').status_code == 200
        response = client.post('/api/plaid/exchange', json={'public_token': 'temporary'})
        response.raise_for_status()
        assert 'private-bank-access-token' not in response.text
        assert 'private-bank-access-token' not in provider.states[company['id']]['payload']
        plaintext = json.loads(cipher().decrypt(provider.states[company['id']]['payload'].encode()))
        assert plaintext['imports']['plaid_items']['bank-item'] == 'private-bank-access-token'
    with TestClient(create_app(auth_backend=provider), headers=headers) as restarted:
        assert restarted.get('/api/plaid/status').json()['banks_connected'] == 1
        restarted.post('/api/plaid/refresh').raise_for_status()
        assert used_tokens == ['private-bank-access-token', 'private-bank-access-token']
        assert restarted.get('/api/plaid/status', headers={'X-Company-ID': second['id']}).json()['banks_connected'] == 0
        restarted.post('/api/plaid/link-token').raise_for_status()
    assert owners == [f"{session['user']['id']}:{company['id']}"] * 2
