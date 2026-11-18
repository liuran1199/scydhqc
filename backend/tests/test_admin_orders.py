from app.models import Admin, Order, Product
from app.utils.security import hash_password


def setup_(client, db, n=2):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    p = Product(name="米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on")
    db.add_all([p])
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    order_ids = []
    for i in range(n):
        client.get(f"/api/auth/dev-login?empid=T00{i}&name=老师{i}")
        r = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": 1 + i}]})
        order_ids.append(r.json()["id"])
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    return order_ids


def test_search_by_code_and_empid(client, db):
    ids = setup_(client, db)
    code = db.get(Order, ids[0]).pickup_code
    assert client.get(f"/api/admin/orders?q={code}").json()["total"] == 1
    assert client.get("/api/admin/orders?q=T001").json()["total"] == 1
    assert client.get("/api/admin/orders?status=PENDING").json()["total"] == 2


def test_batch_ready(client, db):
    ids = setup_(client, db)
    r = client.post("/api/admin/orders/ready", json={"ids": ids + [99999]})
    d = r.json()
    assert d["updated"] == 2 and d["failed"][0]["id"] == 99999
    assert db.get(Order, ids[0]).status == "READY"


def test_ready_idempotent_reports_failed(client, db):
    ids = setup_(client, db, n=1)
    client.post("/api/admin/orders/ready", json={"ids": ids})
    d = client.post("/api/admin/orders/ready", json={"ids": ids}).json()
    assert d["updated"] == 0 and len(d["failed"]) == 1  # 已是 READY，报告原因


def test_admin_cancel_with_reason(client, db):
    ids = setup_(client, db, n=1)
    r = client.post(f"/api/admin/orders/{ids[0]}/cancel", json={"reason": "缺货"})
    assert r.status_code == 200
    o = db.get(Order, ids[0])
    assert o.status == "CANCELLED" and o.cancel_reason == "管理员取消：缺货"


def test_picking_list_xlsx(client, db):
    setup_(client, db)
    r = client.get("/api/admin/orders/picking-list.xlsx")
    assert r.status_code == 200 and len(r.content) > 1000


def test_picking_list_writes_admin_log(client, db):
    """备货清单导出必须落操作日志（I-3）。"""
    from app.models import AdminLog
    setup_(client, db)
    assert client.get("/api/admin/orders/picking-list.xlsx").status_code == 200
    log = db.query(AdminLog).filter_by(action="export").first()
    assert log is not None and log.target == "picking-list"
