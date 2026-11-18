from datetime import datetime

from app.models import Order, Product


def make_order(client, db, empid="T001", qty=2, stock=None):
    p = Product(name="大米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on", stock=stock)
    db.add(p)
    db.commit()
    client.get(f"/api/auth/dev-login?empid={empid}&name=张老师")
    r = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": qty}]})
    return r.json()


def test_list_and_filter(client, db):
    make_order(client, db)
    r = client.get("/api/orders")
    assert r.json()["total"] == 1
    assert client.get("/api/orders?status=PENDING").json()["total"] == 1
    assert client.get("/api/orders?status=DONE").json()["total"] == 0


def test_other_user_order_404(client, db):
    d = make_order(client, db, empid="T001")
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    assert client.get(f"/api/orders/{d['id']}").status_code == 404
    assert client.post(f"/api/orders/{d['id']}/cancel").status_code == 404


def test_cancel_pending_restocks(client, db):
    d = make_order(client, db, stock=10)
    r = client.post(f"/api/orders/{d['id']}/cancel")
    assert r.status_code == 200
    db.expire_all()
    order = db.get(Order, d["id"])
    assert order.status == "CANCELLED" and order.cancel_reason == "用户取消"
    assert db.query(Product).first().stock == 10  # 回补


def test_cancel_done_conflict(client, db):
    d = make_order(client, db)
    order = db.get(Order, d["id"])
    order.status, order.done_at = "DONE", datetime.now()
    db.commit()
    r = client.post(f"/api/orders/{d['id']}/cancel")
    assert r.status_code == 409 and "已核销" not in r.json()["detail"]  # 状态提示文案
    assert "取消" in r.json()["detail"]


def test_cancel_ready_ok(client, db):
    d = make_order(client, db)
    order = db.get(Order, d["id"])
    order.status, order.ready_at = "READY", datetime.now()
    db.commit()
    assert client.post(f"/api/orders/{d['id']}/cancel").status_code == 200
