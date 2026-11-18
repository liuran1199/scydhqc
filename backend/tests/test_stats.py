from datetime import datetime

from app.models import Admin, Order, OrderItem, Product, User
from app.utils.security import hash_password


def admin_login(client, db):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def make_orders(db, n_done=2, amount=6620):
    u = User(empid="T001", name="张老师")
    db.add(u)
    db.commit()
    for i in range(n_done):
        p = Product(name=f"米{i}", spec="5kg", unit="袋", price_original=6750,
                    price_sale=amount, status="on")
        db.add(p)
        db.flush()
        o = Order(order_no=f"20261118-{i+1:06d}", user_id=u.id, status="DONE",
                  total=amount, pickup_code=f"{100000+i}",
                  done_at=datetime.now(), verified_by=1)
        db.add(o)
        db.flush()
        db.add(OrderItem(order_id=o.id, product_id=p.id, p_name=f"米{i}",
                         p_spec="5kg", p_unit="袋", p_price=amount, qty=1,
                         subtotal=amount))
    db.add(Order(order_no="20261118-000099", user_id=u.id, status="PENDING",
                 total=amount, pickup_code="999999"))
    db.commit()


def test_dashboard(client, db):
    make_orders(db, n_done=2)
    admin_login(client, db)
    d = client.get("/api/admin/stats/dashboard").json()
    assert d["pending"] == 1
    assert d["today_done_count"] == 2
    assert d["today_done_amount"] == 6620 * 2
    assert len(d["last7"]) == 7


def test_range_stats_and_ranking(client, db):
    make_orders(db, n_done=2)
    admin_login(client, db)
    today = datetime.now().strftime("%Y-%m-%d")
    d = client.get(f"/api/admin/stats?date_from={today}&date_to={today}").json()
    assert d["done_count"] == 2 and d["done_amount"] == 13240
    assert d["top_products"][0]["name"] == "米0"


def test_export_xlsx(client, db):
    make_orders(db, n_done=1)
    admin_login(client, db)
    today = datetime.now().strftime("%Y-%m-%d")
    r = client.get(f"/api/admin/stats/export?date_from={today}&date_to={today}")
    assert r.status_code == 200 and len(r.content) > 1000
