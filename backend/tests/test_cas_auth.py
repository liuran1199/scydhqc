from app.auth.cas import FakeCASClient  # 测试用实现


def test_callback_creates_user_and_session(client, db):
    client.app.dependency_overrides[get_cas_client_dep()] = lambda: FakeCASClient(
        {"t1": ("T001", "张老师")}
    )
    r = client.get("/api/auth/cas/callback?ticket=t1", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/m/")
    assert "sc_session" in r.cookies
    me = client.get("/api/auth/me")
    assert me.json()["empid"] == "T001" and me.json()["name"] == "张老师"
    client.app.dependency_overrides.clear()


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_dev_login_disabled(client):
    from app.config import settings
    settings.dev_auth_enabled = False
    assert client.get("/api/auth/dev-login?empid=T9").status_code == 403
    settings.dev_auth_enabled = True


def test_update_profile_name(client):
    client.get("/api/auth/dev-login?empid=T002")  # 无姓名登录
    assert client.get("/api/auth/me").json()["name"] is None
    r = client.put("/api/auth/me", json={"name": "李老师"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["name"] == "李老师"


def get_cas_client_dep():
    from app.routers.auth import get_cas_client
    return get_cas_client
