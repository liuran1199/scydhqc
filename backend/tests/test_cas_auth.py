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


def test_user_cookie_secure_over_https(client, db):
    """https 下用户会话 cookie 必须带 Secure（I-4）。"""
    r = client.get("/api/auth/dev-login?empid=T001",
                   headers={"x-forwarded-proto": "https"})
    assert r.status_code == 200
    assert "secure" in r.headers["set-cookie"].lower()


def test_callback_retry_limit_breaks_loop(client, db):
    """CAS 连续失败 3 次必须终止重定向循环，给明确错误（I-5）。"""
    client.app.dependency_overrides[get_cas_client_dep()] = lambda: FakeCASClient({})
    r1 = client.get("/api/auth/cas/callback?ticket=bad", follow_redirects=False)
    r2 = client.get("/api/auth/cas/callback?ticket=bad", follow_redirects=False)
    assert r1.status_code == 302 and r2.status_code == 302  # 前两次静默重试
    r3 = client.get("/api/auth/cas/callback?ticket=bad", follow_redirects=False)
    assert r3.status_code == 502  # 第三次终止，不再 302
    assert "CAS" in r3.json()["detail"] or "稍后" in r3.json()["detail"]
    client.app.dependency_overrides.clear()


def test_callback_success_resets_fail_counter(client, db):
    """失败后成功登录要清零计数，不误伤下一次网络抖动。"""
    client.app.dependency_overrides[get_cas_client_dep()] = lambda: FakeCASClient(
        {"good": ("T001", "张老师")})
    client.get("/api/auth/cas/callback?ticket=bad1", follow_redirects=False)
    client.get("/api/auth/cas/callback?ticket=bad2", follow_redirects=False)
    r = client.get("/api/auth/cas/callback?ticket=good", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].endswith("/m/")
    assert "cas_fails" not in {c.name for c in client.cookies.jar}
    client.app.dependency_overrides.clear()
