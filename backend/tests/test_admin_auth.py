from datetime import datetime, timedelta

from app.models import Admin
from app.utils.security import hash_password


def make_admin(db, username="admin", role="super", active=True):
    """upsert：startup 会预置 initial admin（username=admin），直接 insert 会撞唯一键。"""
    a = db.query(Admin).filter_by(username=username).first()
    if a:
        a.password_hash = hash_password("pass123")
        a.role = role
        a.is_active = active
    else:
        db.add(Admin(username=username, password_hash=hash_password("pass123"),
                     role=role, name=username, is_active=active))
    db.commit()


def login(client, u="admin", p="pass123"):
    return client.post("/api/admin/auth/login", json={"username": u, "password": p})


def test_login_ok_and_me(client, db):
    make_admin(db)
    r = login(client)
    assert r.status_code == 200 and "sc_admin" in r.cookies
    assert client.get("/api/admin/auth/me").json()["username"] == "admin"


def test_lockout_after_5_failures(client, db):
    make_admin(db)
    for _ in range(4):
        assert login(client, p="wrong").status_code == 401
    assert login(client, p="wrong").status_code == 403  # 第 5 次失败即锁定并提示
    assert login(client).status_code == 403  # 密码正确也不解锁
    admin = db.query(Admin).filter_by(username="admin").first()
    assert admin.locked_until > datetime.now()


def test_lock_expiry_allows_login(client, db):
    make_admin(db)
    for _ in range(5):
        login(client, p="wrong")
    admin = db.query(Admin).filter_by(username="admin").first()
    admin.locked_until = datetime.now() - timedelta(seconds=1)
    db.commit()
    assert login(client).status_code == 200


def test_inactive_admin_rejected(client, db):
    make_admin(db, active=False)
    assert login(client).status_code == 403


def test_require_super_blocks_operator(client, db):
    make_admin(db, username="op", role="operator")
    login(client, "op")
    r = client.get("/api/admin/admins")
    assert r.status_code == 403          # Task 14 接口已建，operator 被拒


def test_register_fail_counts_atomically(db):
    """失败计数用 SQL 原子自增：多会话交错不丢计数（I-1）。"""
    from app.routers.admin_auth import _register_fail
    make_admin(db)
    a = db.query(Admin).filter_by(username="admin").first()
    for _ in range(3):
        _register_fail(db, a.id)
        db.commit()
    db.refresh(a)
    assert a.failed_attempts == 3 and a.locked_until is None


def test_register_fail_locks_at_threshold(db):
    from app.routers.admin_auth import _register_fail
    make_admin(db)
    a = db.query(Admin).filter_by(username="admin").first()
    for _ in range(5):
        _register_fail(db, a.id)
        db.commit()
    db.refresh(a)
    assert a.locked_until is not None and a.locked_until > datetime.now()
    assert a.failed_attempts == 0  # 锁定即清零，期满重新累计
