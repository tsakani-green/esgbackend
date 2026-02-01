import requests


BASE = 'http://localhost:8002'


def test_ai_assistant_returns_summary_for_seeded_user():
    # login as seeded demo user
    login = requests.post(f'{BASE}/api/auth/login', data={'username': 'bertha-user', 'password': 'bertha123'}, timeout=5)
    assert login.status_code == 200
    token = login.json()['access_token']

    payload = {
        'instruction': 'Produce a 3-line executive summary focusing on carbon and quick wins',
        'mode': 'summary'
    }
    resp = requests.post(f'{BASE}/api/ai/assistant', json=payload, headers={'Authorization': f'Bearer {token}'}, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert ('summary' in data or 'text' in data) and data.get('summary', data.get('text'))
