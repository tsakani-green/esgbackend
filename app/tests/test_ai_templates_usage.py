import requests

BASE = 'http://localhost:8002'


def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", data={"username": username, "password": password}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def test_ai_assistant_respects_template_key():
    # create a short public template as admin
    admin_token = login('admin', 'admin123')
    tpl = {
        "key": "test_exec_summary",
        "name": "Test Exec Summary",
        "prompt": "Provide a 2-line summary for {{portfolio_name}} focusing on carbon and one quick win.",
        "is_public": True
    }

    resp = requests.post(f"{BASE}/api/admin/portfolios/bertha-house/ai-templates", json=tpl,
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=5)
    assert resp.status_code in (200, 201)

    # call assistant as a client using the template_key
    client_token = login('bertha-user', 'bertha123')
    payload = {"template_key": "test_exec_summary", "clientId": "bertha-house"}
    r = requests.post(f"{BASE}/api/ai/assistant", json=payload,
                      headers={"Authorization": f"Bearer {client_token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    # backend should report which template was used
    assert data.get('used_template') == 'test_exec_summary'
    assert data.get('result') and (data['result'].get('answer') or data['result'].get('summary') or data.get('summary'))
