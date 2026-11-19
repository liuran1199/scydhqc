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


def test_picking_list_json(client, db):
    setup_(client, db)
    r = client.get("/api/admin/orders/picking-list")
    assert r.status_code == 200
    body = r.json()
    assert body["total_orders"] == len(body["orders"])
    assert sum(row["qty"] for row in body["summary"]) == body["total_qty"]


def test_picking_list_writes_admin_log(client, db):
    """备货清单打印必须落操作日志（I-3）。"""
    from app.models import AdminLog
    setup_(client, db)
    assert client.get("/api/admin/orders/picking-list").status_code == 200
    log = db.query(AdminLog).filter_by(action="export").first()
    assert log is not None and log.target == "picking-list"


def test_order_by_code(client, db):
    """窗口按取货码查单：命中带订货人，未命中 404"""
    ids = setup_(client, db, n=1)
    code = db.get(Order, ids[0]).pickup_code
    r = client.get(f"/api/admin/orders/by-code/{code}")
    assert r.status_code == 200
    assert r.json()["user"]["name"] == "老师0"
    assert client.get("/api/admin/orders/by-code/000000").status_code == 404


def test_verify_endpoints_require_admin(db):
    """核销双接口必须管理员鉴权：取货码会随二维码暴露，接口不能裸奔。"""
    from fastapi.testclient import TestClient

    from app.main import app

    anon = TestClient(app)  # 全新会话，未登录任何管理员
    assert anon.get("/api/admin/orders/by-code/000000").status_code == 401
    assert anon.post("/api/admin/orders/complete", json={"code": "000000"}).status_code == 401


def test_complete_by_code(client, db):
    """窗口核销：PENDING 可直接核销为 DONE，重复核销 409，落操作日志"""
    from app.models import AdminLog
    ids = setup_(client, db, n=1)
    code = db.get(Order, ids[0]).pickup_code
    r = client.post("/api/admin/orders/complete", json={"code": code})
    assert r.status_code == 200
    o = db.get(Order, ids[0])
    assert o.status == "DONE" and o.done_at is not None
    assert client.post("/api/admin/orders/complete", json={"code": code}).status_code == 409
    log = db.query(AdminLog).filter_by(action="complete").first()
    assert log is not None and log.target == o.order_no


def test_invalid_date_params_return_400(client, db):
    """非法日期参数应 400 提示，而不是 fromisoformat 抛 500。"""
    setup_(client, db, n=1)
    assert client.get("/api/admin/orders?pickup_date=not-a-date").status_code == 400
    assert client.get("/api/admin/orders?date_from=xx").status_code == 400
    assert client.get("/api/admin/orders/receipts?pickup_date=2026-13-99").status_code == 400
    assert client.get("/api/admin/orders/picking-list?pickup_date=oops").status_code == 400


def test_receipts_rejects_over_limit(client, db):
    """超过单次打印上限必须明确报错，不能静默截断漏单。"""
    setup_(client, db, n=1)
    ids = ",".join(str(i) for i in range(1, 502))  # 501 个 id
    r = client.get(f"/api/admin/orders/receipts?ids={ids}")
    assert r.status_code == 400 and "500" in r.json()["detail"]
