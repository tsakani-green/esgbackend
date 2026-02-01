import requests

BASE = 'http://localhost:8002'


def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", data={"username": username, "password": password}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def test_ai_templates_crud_lifecycle():
    admin_token = login('admin', 'admin123')
    client_token = login('bertha-user', 'bertha123')

    portfolio = 'bertha-house'
    tpl = {
        'key': 'crud_test_tpl',
        'name': 'CRUD Test Template',
        'prompt': 'CRUD test for {{portfolio_name}}',
        'is_public': True
    }

    # create
    r = requests.post(f"{BASE}/api/admin/portfolios/{portfolio}/ai-templates", json=tpl, headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
    assert r.status_code in (200, 201)

    # list (client should see public template)
    r = requests.get(f"{BASE}/api/ai/templates/{portfolio}", headers={'Authorization': f'Bearer {client_token}'}, timeout=5)
    assert r.status_code == 200
    templates = r.json().get('templates', [])
    assert any(t['key'] == 'crud_test_tpl' for t in templates)

    # update
    tpl['prompt'] = 'Updated prompt for CRUD test {{portfolio_name}}'
    r = requests.post(f"{BASE}/api/admin/portfolios/{portfolio}/ai-templates", json=tpl, headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
    assert r.status_code == 200

    # unpublish (set is_public false) and confirm client no longer sees it
    tpl['is_public'] = False
    r = requests.post(f"{BASE}/api/admin/portfolios/{portfolio}/ai-templates", json=tpl, headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
    assert r.status_code == 200

    r = requests.get(f"{BASE}/api/ai/templates/{portfolio}", headers={'Authorization': f'Bearer {client_token}'}, timeout=5)
    assert r.status_code == 200
    templates = r.json().get('templates', [])
    assert not any(t['key'] == 'crud_test_tpl' and t.get('is_public') for t in templates)

    # delete
    r = requests.delete(f"{BASE}/api/admin/portfolios/{portfolio}/ai-templates/crud_test_tpl", headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
    assert r.status_code == 200

    # confirm deletion
    r = requests.get(f"{BASE}/api/ai/templates/{portfolio}", headers={'Authorization': f'Bearer {admin_token}'}, timeout=5)
    assert r.status_code == 200
    templates = r.json().get('templates', [])
    assert not any(t['key'] == 'crud_test_tpl' for t in templates)
