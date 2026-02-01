import requests
import io

BASE = 'http://localhost:8002'


def login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", data={"username": username, "password": password}, timeout=5)
    r.raise_for_status()
    return r.json()["access_token"]


def make_csv(rows):
    buf = io.StringIO()
    headers = ['invoice_number','vendor_name','invoice_date','total_amount','currency']
    buf.write(','.join(headers) + '\n')
    for r in rows:
        buf.write(','.join([str(r.get(h, '')) for h in headers]) + '\n')
    buf.seek(0)
    return buf


def test_bulk_upload_csv_idempotent():
    token = login('bertha-user', 'bertha123')

    rows = [
        { 'invoice_number': 'BULK-2026-001', 'vendor_name': 'Acme Supplies', 'invoice_date': '2025-12-01', 'total_amount': '1234.50', 'currency': 'ZAR' },
        { 'invoice_number': 'BULK-2026-002', 'vendor_name': 'GreenPower', 'invoice_date': '2025-11-15', 'total_amount': '9876.00', 'currency': 'ZAR' },
    ]

    csv_buf = make_csv(rows)

    files = {
        'files': ('invoices.csv', csv_buf.getvalue(), 'text/csv')
    }

    # first upload
    r = requests.post(f"{BASE}/api/invoices/invoice-bulk-upload", files=files, headers={'Authorization': f'Bearer {token}'}, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert data['successful_uploads'] >= 2
    first_count = len(data['processed_invoices'])

    # upload same file again -> should not create duplicates (idempotent)
    csv_buf.seek(0)
    files = {
        'files': ('invoices.csv', csv_buf.getvalue(), 'text/csv')
    }
    r2 = requests.post(f"{BASE}/api/invoices/invoice-bulk-upload", files=files, headers={'Authorization': f'Bearer {token}'}, timeout=20)
    assert r2.status_code == 200
    data2 = r2.json()

    # processed_invoices should be the same keys (no duplicate keys created)
    assert set(data['processed_invoices']) == set(data2['processed_invoices'])

    # cleanup: ensure entries exist in DB via load endpoint
    r3 = requests.get(f"{BASE}/api/invoices", headers={'Authorization': f'Bearer {token}'}, params={'months':12}, timeout=10)
    assert r3.status_code == 200
    invoices = r3.json().get('invoices') or []
    assert any(i.get('invoice_number') == 'BULK-2026-001' for i in invoices)
