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
