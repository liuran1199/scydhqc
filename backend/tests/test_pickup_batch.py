"""16 点截单：取货批次 pickup_date 规则 + 备货清单/小票接口按批次出数据。"""
from datetime import date, timedelta

from app.models import Admin, Order, Product
from app.services.orders import pickup_date_for
from app.utils.security import hash_password


def test_pickup_date_rule():
    """15:59 → 次日；16:00 起（含边界）→ 隔日；深夜/凌晨均符合规则"""
    d = __import__("datetime").datetime(2026, 11, 19)
    assert pickup_date_for(d.replace(hour=15, minute=59)) == date(2026, 11, 20)
    assert pickup_date_for(d.replace(hour=16)) == date(2026, 11, 21)  # 恰好 16 点属后一批
    assert pickup_date_for(d.replace(hour=23, minute=30)) == date(2026, 11, 21)
    assert pickup_date_for(d.replace(hour=0, minute=1)) == date(2026, 11, 20)


def seed_and_order(client, db):
    p = Product(name="米", spec="5kg", unit="袋", price_original=6750,
                price_sale=6620, status="on")
    db.add(p)
    db.commit()
    client.get("/api/auth/dev-login?empid=T001&name=张老师")
    r = client.post("/api/orders", json={"items": [{"product_id": p.id, "qty": 1}]})
    assert r.status_code == 200
    return r.json()


def _admin_login(client, db):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def test_create_order_sets_pickup_date(client, db):
    """下单即落取货批次，且序列化返回给前端"""
    d = seed_and_order(client, db)
    o = db.get(Order, d["id"])
    assert o.pickup_date == pickup_date_for(o.created_at)
    assert d["pickup_date"] == o.pickup_date.isoformat()


def test_admin_filter_by_pickup_date(client, db):
    d = seed_and_order(client, db)
    _admin_login(client, db)
    o = db.get(Order, d["id"])
    other = (o.pickup_date + timedelta(days=1)).isoformat()
    assert client.get(f"/api/admin/orders?pickup_date={o.pickup_date}").json()["total"] == 1
    assert client.get(f"/api/admin/orders?pickup_date={other}").json()["total"] == 0


def test_admin_filter_by_multi_status(client, db):
    """status 支持逗号分隔（备货角标 PENDING,READY 与小票同口径）"""
    d = seed_and_order(client, db)
    _admin_login(client, db)
    o = db.get(Order, d["id"])
    assert client.get("/api/admin/orders?status=PENDING,READY").json()["total"] == 1
    o.status = "DONE"
    db.commit()
    assert client.get("/api/admin/orders?status=PENDING,READY").json()["total"] == 0
    assert client.get("/api/admin/orders?status=DONE").json()["total"] == 1


def test_picking_list_scoped_to_batch(client, db):
    """备货清单只含指定批次，且按商品聚合数量"""
    d1 = seed_and_order(client, db)
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    r2 = client.post("/api/orders", json={"items": [{"product_id": db.query(Product).first().id,
                                                     "qty": 2}]})
    o1, o2 = db.get(Order, d1["id"]), db.get(Order, r2.json()["id"])
    batch = o1.pickup_date
    o2.pickup_date = batch + timedelta(days=1)  # 挪到别的批次
    db.commit()
    _admin_login(client, db)
    r = client.get(f"/api/admin/orders/picking-list?pickup_date={batch}").json()
    nos = [o["order_no"] for o in r["orders"]]
    assert d1["order_no"] in nos and r2.json()["order_no"] not in nos
    # 两单的商品/数量聚合到 summary（seed_and_order 下 1 件 + 本单 2 件）
    assert r["total_orders"] == 1
    assert sum(row["qty"] for row in r["summary"]) == sum(
        i["qty"] for o in r["orders"] for i in o["items"])


def test_picking_list_defaults_to_tomorrow_batch(client, db):
    """不传日期默认今晚要备的批次（明天取货）"""
    d = seed_and_order(client, db)
    _admin_login(client, db)
    o = db.get(Order, d["id"])
    o.pickup_date = date.today() + timedelta(days=1)
    db.commit()
    r = client.get("/api/admin/orders/picking-list").json()
    assert d["order_no"] in [o["order_no"] for o in r["orders"]]


def test_receipts_by_batch_ids_and_validation(client, db):
    """小票数据接口：按批次 / 按 ids / 都不给 400，且带订货人信息"""
    d1 = seed_and_order(client, db)
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    r2 = client.post("/api/orders", json={"items": [{"product_id": db.query(Product).first().id,
                                                     "qty": 2}]})
    o1, o2 = db.get(Order, d1["id"]), db.get(Order, r2.json()["id"])
    o2.pickup_date = o1.pickup_date + timedelta(days=1)
    db.commit()
    _admin_login(client, db)

    r = client.get(f"/api/admin/orders/receipts?pickup_date={o1.pickup_date}")
    items = r.json()["items"]
    assert [i["id"] for i in items] == [o1.id]
    assert items[0]["user"]["name"] == "张老师"  # 小票要钉在袋子上，必须带姓名

    r = client.get(f"/api/admin/orders/receipts?ids={o2.id}")
    assert [i["id"] for i in r.json()["items"]] == [o2.id]

    assert client.get("/api/admin/orders/receipts").status_code == 400
