from datetime import datetime

from app.models import Admin, Order, Product
from app.utils.security import hash_password


def setup_(client, db, status="READY"):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    p = Product(name="米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on")
    db.add_all([p])
    db.commit()
    client.get("/api/auth/dev-login?empid=T001&name=张老师")
    d = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": 2}]}).json()
    if status != "PENDING":
        o = db.get(Order, d["id"])
        o.status = status
        if status == "DONE":
            o.done_at = datetime.now()
        db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    return d


def test_lookup_by_code_and_qr(client, db):
    d = setup_(client, db)
    r = client.get(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 200 and r.json()["order"]["id"] == d["id"]
    qr = f"SC:{d['order_no']}:{d['pickup_code']}"
    assert client.get(f"/api/admin/verify/{qr}").json()["order"]["id"] == d["id"]


def test_verify_ok_records_admin(client, db):
    d = setup_(client, db)
    adm = db.query(Admin).filter_by(username="adm").first()
    r = client.post(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 200
    o = db.get(Order, d["id"])
    assert o.status == "DONE" and o.done_at and o.verified_by == adm.id


def test_verify_twice(client, db):
    d = setup_(client, db, status="DONE")
    r = client.post(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 409 and "已完成" in r.json()["detail"]


def test_verify_pending_hint(client, db):
    d = setup_(client, db, status="PENDING")
    r = client.post(f"/api/admin/verify/{d['pickup_code']}")
    assert r.status_code == 409 and "待备货" in r.json()["detail"]


def test_verify_cancelled(client, db):
    d = setup_(client, db, status="CANCELLED")
    assert client.post(f"/api/admin/verify/{d['pickup_code']}").status_code == 409


def test_unknown_code_404(client, db):
    setup_(client, db)
    assert client.post("/api/admin/verify/000001").status_code in (404, 409)
