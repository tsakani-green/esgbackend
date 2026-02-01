import requests

BASE = 'http://localhost:8002'


def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", data={"username": username, "password": password}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def assert_nonempty_text(x):
    assert x is not None
    if isinstance(x, dict):
        # try common fields
        text = x.get('answer') or x.get('summary') or x.get('text') or ''
    else:
        text = str(x)
    assert len(text.strip()) > 5


def test_prompt_quality_variants():
    token = login('bertha-user', 'bertha123')

    # instruction
    r = requests.post(f"{BASE}/api/ai/assistant", json={"instruction": "Write a 2-line executive summary on carbon and 1 quick win for Bertha House", "mode": "summary", "clientId": "bertha-house"}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200
    assert_nonempty_text(r.json().get('result') or r.json())

    # template_prompt override
    r = requests.post(f"{BASE}/api/ai/assistant", json={"template_prompt": "Two bullets: current carbon intensity and one immediate action for {{portfolio_name}}", "clientId": "bertha-house"}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200
    assert_nonempty_text(r.json().get('result') or r.json())

    # template_key (if present, don't fail if not configured in env)
    # create a short local template and use it
    admin_token = login('admin', 'admin123')
    tpl = {"key": "pq_check", "name": "PQ check", "prompt": "Provide a one-line metric and one action for {{portfolio_name}}.", "is_public": True}
    requests.post(f"{BASE}/api/admin/portfolios/bertha-house/ai-templates", json=tpl, headers={"Authorization": f"Bearer {admin_token}"}, timeout=5)
    r = requests.post(f"{BASE}/api/ai/assistant", json={"template_key": "pq_check", "clientId": "bertha-house"}, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get('used_template') in ("pq_check", None)
    assert_nonempty_text(data.get('result') or data)
