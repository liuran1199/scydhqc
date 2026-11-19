from app.models import Admin
from app.utils.security import hash_password


def super_login(client, db):
    db.add(Admin(username="root", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "root", "password": "p"})


def test_create_admin_then_login(client, db):
    super_login(client, db)
    r = client.post("/api/admin/admins", json={
        "username": "op1", "password": "op12345", "role": "operator", "name": "操作员"})
    assert r.status_code == 200
    client.post("/api/admin/auth/logout")
    r = client.post("/api/admin/auth/login", json={"username": "op1", "password": "op12345"})
    assert r.status_code == 200


def test_operator_cannot_manage(client, db):
    super_login(client, db)
    client.post("/api/admin/admins",
                json={"username": "op", "password": "x12345", "role": "operator"})
    client.post("/api/admin/auth/logout")
    client.post("/api/admin/auth/login", json={"username": "op", "password": "x12345"})
    assert client.get("/api/admin/admins").status_code == 403


def test_reset_password_and_disable(client, db):
    super_login(client, db)
    aid = client.post("/api/admin/admins", json={
        "username": "op2", "password": "old123", "role": "operator"}).json()["id"]
    client.put(f"/api/admin/admins/{aid}", json={"password": "new123"})
    client.post("/api/admin/auth/logout")
    assert client.post("/api/admin/auth/login",
                       json={"username": "op2", "password": "new123"}).status_code == 200
    client.post("/api/admin/auth/logout")
    client.post("/api/admin/auth/login", json={"username": "root", "password": "p"})
    client.put(f"/api/admin/admins/{aid}", json={"is_active": False})
    client.post("/api/admin/auth/logout")
    assert client.post("/api/admin/auth/login",
                       json={"username": "op2", "password": "new123"}).status_code == 403


def test_notice_roundtrip(client, db):
    super_login(client, db)
    client.put("/api/admin/settings/notice",
               json={"content": "服务点：综合楼一层\n时间：工作日 14:00-17:00"})
    client.get("/api/auth/dev-login?empid=T001")
    r = client.get("/api/notice")
    assert r.status_code == 200
    assert "综合楼一层" in r.json()["content"]


def test_password_change_revokes_old_sessions(client, db):
    """改密必须让旧会话 cookie 全部失效（防泄露 cookie 在改密后继续可用）。"""
    super_login(client, db)
    aid = client.post("/api/admin/admins", json={
        "username": "op3", "password": "old123", "role": "operator"}).json()["id"]
    client.post("/api/admin/auth/logout")
    client.post("/api/admin/auth/login", json={"username": "op3", "password": "old123"})
    assert client.get("/api/admin/auth/me").status_code == 200  # 会话有效
    op3_cookie = client.cookies.get("sc_admin")  # op3 浏览器的旧会话
    # 同一测试进程里再用超管身份改 op3 的密码（模拟另一台管理机操作）
    client.post("/api/admin/auth/logout")
    client.post("/api/admin/auth/login", json={"username": "root", "password": "p"})
    client.put(f"/api/admin/admins/{aid}", json={"password": "new123"})
    # 把 op3 的旧 cookie 放回去（等价于已泄露的旧会话）：必须 401
    client.cookies.set("sc_admin", op3_cookie)
    assert client.get("/api/admin/auth/me").status_code == 401


def test_last_super_admin_protected(client, db):
    """最后一个有效超管不可停用/降级，否则系统无人可管。"""
    super_login(client, db)
    # 测试库启动时内置了 admin 超管，先停用它，制造"只剩 root 一个有效超管"
    init = db.query(Admin).filter_by(username="admin").first()
    assert client.put(f"/api/admin/admins/{init.id}", json={"is_active": False}).status_code == 200
    root = db.query(Admin).filter_by(username="root").first()
    assert client.put(f"/api/admin/admins/{root.id}",
                      json={"is_active": False}).status_code == 400
    assert client.put(f"/api/admin/admins/{root.id}",
                      json={"role": "operator"}).status_code == 400
    # 有第二个超管时可以降级
    client.post("/api/admin/admins", json={"username": "s2", "password": "s12345",
                                           "role": "super"})
    assert client.put(f"/api/admin/admins/{root.id}",
                      json={"role": "operator"}).status_code == 200


def test_update_admin_validates_role_and_password(client, db):
    super_login(client, db)
    aid = client.post("/api/admin/admins", json={
        "username": "op4", "password": "x12345", "role": "operator"}).json()["id"]
    assert client.put(f"/api/admin/admins/{aid}",
                      json={"role": "boss"}).status_code == 400
    assert client.put(f"/api/admin/admins/{aid}",
                      json={"password": "123"}).status_code == 400
