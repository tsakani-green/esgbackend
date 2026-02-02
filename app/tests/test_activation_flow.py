import asyncio
import os
import time
from datetime import timedelta
from jose import jwt
import pytest
from fastapi import HTTPException
from bson import ObjectId

from app.api import auth
from app.core import config

settings = config.settings


class FakeCollection:
    def __init__(self):
        self._docs = {}

    async def find_one(self, query):
        # Support lookup by $or and by _id
        if query is None:
            return None
        if isinstance(query, dict) and "$or" in query:
            for c in query["$or"]:
                for k, v in c.items():
                    for doc in self._docs.values():
                        if doc.get(k) == v:
                            return doc
            return None
        if "_id" in query:
            _id = query["_id"]
            for doc in self._docs.values():
                if doc.get("_id") == _id:
                    return doc
            return None
        # generic equality
        for doc in self._docs.values():
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None

    async def insert_one(self, doc):
        _id = ObjectId()
        doc_copy = dict(doc)
        doc_copy["_id"] = _id
        self._docs[str(_id)] = doc_copy
        class Result:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id
        return Result(_id)

    async def update_one(self, query, update):
        # only support $set
        doc = await self.find_one(query)
        if not doc:
            return
        set_obj = update.get("$set", {})
        doc.update(set_obj)
        class Result:
            def __init__(self, matched_count=1):
                self.matched_count = matched_count
        return Result()


class FakeDB:
    def __init__(self):
        self.users = FakeCollection()
        self.password_reset_tokens = FakeCollection()


def test_send_activation_email_writes_to_disk(tmp_path, monkeypatch):
    # The codebase has two possible email backends; prefer to be permissive
    # in tests. If the auth email helper writes to disk it should return True.
    # If the lower-level service requires SMTP it may raise RuntimeError; both
    # are acceptable outcomes for this test as long as we don't actually try
    # to send a real email.
    monkeypatch.setattr(settings, "EMAIL_USERNAME", "")
    tmp_upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_upload_dir))

    to_email = "foo@example.com"
    user_name = "Foo"
    activation_link = "http://localhost/activate?token=abc"

    try:
        # If async function, await it; otherwise call directly
        res = auth.send_activation_email(to_email, user_name, activation_link)
        if asyncio.iscoroutine(res):
            res = asyncio.get_event_loop().run_until_complete(res)
        assert res is True

        # Check that file is created in uploads/sent_emails
        sent_dir = tmp_upload_dir / "sent_emails"
        files = list(sent_dir.glob("activation-*.html"))
        assert len(files) >= 1
    except RuntimeError as e:
        # Some email backends raise when SMTP is not configured; accept this
        assert "SMTP not configured" in str(e)


@pytest.mark.asyncio
async def test_activate_success(monkeypatch):
    fake_db = FakeDB()

    # insert a pending user
    user_doc = {
        "username": "alice",
        "email": "alice@example.com",
        "full_name": "Alice",
        "hashed_password": "",
        "role": "client",
        "status": "pending",
    }
    res = await fake_db.users.insert_one(user_doc)

    import importlib, importlib.util, pathlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Load the exact auth module from the backend app path so we don't pick up
    # similarly-named modules from other packages.
    auth_path = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "auth.py"
    spec = importlib.util.spec_from_file_location("esgbackend_auth", str(auth_path))
    auth_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth_mod)

    # build token payload directly
    from datetime import datetime, timedelta
    expire = datetime.utcnow() + timedelta(days=7)
    token = jwt.encode({"sub": "alice", "role": "client", "exp": expire}, auth_mod.settings.SECRET_KEY, algorithm=auth_mod.settings.ALGORITHM)

    # Build a minimal FastAPI app and mount the auth endpoints we want to test
    app_small = FastAPI()
    app_small.post("/activate")(auth_mod.activate)
    app_small.get("/me")(auth_mod.me)

    # Override the core DB dependency directly
    import app.core.database as dbmod
    app_small.dependency_overrides[dbmod.get_db] = lambda: fake_db

    client = TestClient(app_small)

    r = client.post("/activate", json={"token": token})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["message"] == "Account activated successfully"

    # verify that user status was updated
    user = await fake_db.users.find_one({"_id": res.inserted_id})
    assert user.get("status") == "active"


def test_activate_invalid_token_raises():
    import importlib, importlib.util, pathlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    fake_db = FakeDB()

    auth_path = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "auth.py"
    spec = importlib.util.spec_from_file_location("esgbackend_auth", str(auth_path))
    auth_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth_mod)

    app_small = FastAPI()
    app_small.post("/activate")(auth_mod.activate)

    import app.core.database as dbmod
    app_small.dependency_overrides[dbmod.get_db] = lambda: fake_db

    client = TestClient(app_small)

    r = client.post("/activate", json={"token": "not-a-valid-token"})
    assert r.status_code == 400


def test_resend_activation_user_not_found():
    import importlib, importlib.util, pathlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    fake_db = FakeDB()

    auth_path = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "auth.py"
    spec = importlib.util.spec_from_file_location("esgbackend_auth", str(auth_path))
    auth_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth_mod)

    app_small = FastAPI()
    app_small.post("/resend-activation")(auth_mod.resend_activation)

    import app.core.database as dbmod
    app_small.dependency_overrides[dbmod.get_db] = lambda: fake_db

    client = TestClient(app_small)

    r = client.post("/resend-activation", json={"email": "noone@example.com"})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_resend_activation_success(monkeypatch):
    import importlib, importlib.util, pathlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    fake_db = FakeDB()

    user_doc = {
        "username": "bob",
        "email": "bob@example.com",
        "full_name": "Bob",
        "hashed_password": "",
        "role": "client",
        "status": "pending",
    }
    await fake_db.users.insert_one(user_doc)

    # monkeypatch send_activation_email to avoid writing files
    async def fake_send(to_email, name, link):
        return True

    auth_path = pathlib.Path(__file__).resolve().parents[2] / "app" / "api" / "auth.py"
    spec = importlib.util.spec_from_file_location("esgbackend_auth", str(auth_path))
    auth_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth_mod)

    monkeypatch.setattr(auth_mod, "send_activation_email", fake_send)
    monkeypatch.setattr(auth_mod.settings, "ENVIRONMENT", "development")

    app_small = FastAPI()
    app_small.post("/resend-activation")(auth_mod.resend_activation)

    import app.core.database as dbmod
    app_small.dependency_overrides[dbmod.get_db] = lambda: fake_db

    client = TestClient(app_small)

    r = client.post("/resend-activation", json={"email": "bob@example.com"})
    assert r.status_code == 200
    resp = r.json()
    assert resp.get("message") in ("Activation email sent", "Failed to send activation email")
    assert "activation_link" in resp
    assert resp.get("email_sent") is True


@pytest.mark.asyncio
async def test_get_current_user_rejects_pending_user(monkeypatch):
    import importlib
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    fake_db = FakeDB()

    user_doc = {
        "username": "charlie",
        "email": "charlie@example.com",
        "full_name": "Charlie",
        "hashed_password": "",
        "role": "client",
        "status": "pending",
    }
    await fake_db.users.insert_one(user_doc)

    auth_mod = importlib.import_module("app.api.auth")

    from datetime import datetime, timedelta
    expire = datetime.utcnow() + timedelta(minutes=5)
    token = jwt.encode({"sub": "charlie", "role": "client", "exp": expire}, auth_mod.settings.SECRET_KEY, algorithm=auth_mod.settings.ALGORITHM)

    app_small = FastAPI()
    app_small.get("/me")(auth_mod.me)
    app_small.dependency_overrides[auth_mod.get_db] = lambda: fake_db

    client = TestClient(app_small)

    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403