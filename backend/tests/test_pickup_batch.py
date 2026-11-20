"""16 点截单：备货队列规则 + 备货清单/小票接口按队列出数据。

队列制：PENDING 且下单时间 ≤ 截点（16 点前=现在，16 点后=当日16点）。
不依赖取货日期，休息日积压开工即全部呈现。
"""
from datetime import date, timedelta

from app.models import Admin, Order, Product
from app.services.orders import prep_cutoff, pickup_date_for
from app.utils.security import hash_password


def test_pickup_date_rule():
    """15:59 → 次日；16:00 起（含边界）→ 隔日；深夜/凌晨均符合规则（库内参考字段）"""
    d = __import__("datetime").datetime(2026, 11, 19)
    assert pickup_date_for(d.replace(hour=15, minute=59)) == date(2026, 11, 20)
    assert pickup_date_for(d.replace(hour=16)) == date(2026, 11, 21)  # 恰好 16 点属后一批
    assert pickup_date_for(d.replace(hour=23, minute=30)) == date(2026, 11, 21)
    assert pickup_date_for(d.replace(hour=0, minute=1)) == date(2026, 11, 20)


def test_prep_cutoff_rule():
    """截点：16 点前 = 现在；16 点后（含边界）= 当日 16 点"""
    dt = __import__("datetime").datetime
    assert prep_cutoff(dt(2026, 11, 19, 15, 59)) == dt(2026, 11, 19, 15, 59)
    assert prep_cutoff(dt(2026, 11, 19, 16)) == dt(2026, 11, 19, 16)
    assert prep_cutoff(dt(2026, 11, 19, 23, 30)) == dt(2026, 11, 19, 16)


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


def test_picking_list_scoped_to_queue(client, db):
    """备货清单 = PENDING 且下单 ≤ 截点：截点后的新单和已备好的都不在队列里"""
    d1 = seed_and_order(client, db)
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    r2 = client.post("/api/orders", json={"items": [{"product_id": db.query(Product).first().id,
                                                     "qty": 2}]})
    o1, o2 = db.get(Order, d1["id"]), db.get(Order, r2.json()["id"])
    # 与当下时刻解耦：一单挪进截点内，一单挪到截点外（无论测试跑在几点都确定）
    o1.created_at = prep_cutoff() - timedelta(minutes=1)
    o2.created_at = prep_cutoff() + timedelta(minutes=1)
    db.commit()
    _admin_login(client, db)
    r = client.get("/api/admin/orders/picking-list").json()
    nos = [o["order_no"] for o in r["orders"]]
    assert d1["order_no"] in nos and r2.json()["order_no"] not in nos
    assert r["total_orders"] == 1
    assert sum(row["qty"] for row in r["summary"]) == sum(
        i["qty"] for o in r["orders"] for i in o["items"])


def test_picking_list_excludes_ready_and_reports_cutoff(client, db):
    """已备好（READY）的不占队列；返回的截点符合当日规则"""
    from datetime import datetime

    from app.services.orders import PICKUP_CUTOFF_HOUR
    from app.utils.times import now_cst

    d = seed_and_order(client, db)
    o = db.get(Order, d["id"])
    o.created_at = prep_cutoff() - timedelta(minutes=1)
    o.status = "READY"
    db.commit()
    _admin_login(client, db)
    r = client.get("/api/admin/orders/picking-list").json()
    assert d["order_no"] not in [x["order_no"] for x in r["orders"]]
    got = datetime.fromisoformat(r["cutoff"])
    now = now_cst()
    today_cutoff = now.replace(hour=PICKUP_CUTOFF_HOUR, minute=0, second=0, microsecond=0)
    if now >= today_cutoff:
        assert got == today_cutoff  # 16 点后：截点固定为当日 16:00
    else:
        assert (now - got).total_seconds() < 90  # 16 点前：截点=请求时刻（容忍断言耗时）


def test_admin_queue_filter_matches_picking_list(client, db):
    """订单列表 queue=1 与备货清单同口径（后台"看待备"按钮用）"""
    d1 = seed_and_order(client, db)
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    r2 = client.post("/api/orders", json={"items": [{"product_id": db.query(Product).first().id,
                                                     "qty": 1}]})
    o1, o2 = db.get(Order, d1["id"]), db.get(Order, r2.json()["id"])
    o1.created_at = prep_cutoff() - timedelta(minutes=1)
    o2.created_at = prep_cutoff() + timedelta(minutes=1)
    db.commit()
    _admin_login(client, db)
    r = client.get("/api/admin/orders?queue=1").json()
    assert r["total"] == 1 and r["items"][0]["order_no"] == d1["order_no"]


def test_receipts_queue_and_ids(client, db):
    """小票数据：不传参 = 待备队列（带订货人）；按 ids 则精确选择"""
    d1 = seed_and_order(client, db)
    client.get("/api/auth/dev-login?empid=T002&name=李老师")
    r2 = client.post("/api/orders", json={"items": [{"product_id": db.query(Product).first().id,
                                                     "qty": 2}]})
    o1, o2 = db.get(Order, d1["id"]), db.get(Order, r2.json()["id"])
    o1.created_at = prep_cutoff() - timedelta(minutes=1)
    o2.created_at = prep_cutoff() + timedelta(minutes=1)
    db.commit()
    _admin_login(client, db)

    r = client.get("/api/admin/orders/receipts")
    items = r.json()["items"]
    assert [i["id"] for i in items] == [o1.id]
    assert items[0]["user"]["name"] == "张老师"  # 小票要钉在袋子上，必须带姓名

    r = client.get(f"/api/admin/orders/receipts?ids={o2.id}")
    assert [i["id"] for i in r.json()["items"]] == [o2.id]


def test_pickup_info_has_no_date_promise(client, db):
    """确认页接口只给截单小时数，不再承诺具体取货日期"""
    r = client.get("/api/pickup-info")
    assert r.status_code == 200
    body = r.json()
    assert body == {"cutoff_hour": 16}
