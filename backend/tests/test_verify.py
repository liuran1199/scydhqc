"""窗口核销（统一走 /api/admin/orders/by-code + /complete）。

旧 /api/admin/verify 路由已删：它只许 READY 核销、与 complete 的 PENDING+READY
规则不一致，且前端早已全部走 by-code/complete。规则统一为——货在窗口即可核销，
PENDING 直转 DONE，核销人与操作日志同事务留痕。
"""
from app.models import Admin, AdminLog, Order, Product
from app.utils.security import hash_password
from app.utils.times import now_cst


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
            o.done_at = now_cst()
        db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})
    return d


def test_lookup_by_code(client, db):
    d = setup_(client, db)
    r = client.get(f"/api/admin/orders/by-code/{d['pickup_code']}")
    assert r.status_code == 200 and r.json()["id"] == d["id"]


def test_complete_records_admin_and_log(client, db):
    """核销必须留痕：verified_by 落库，操作日志同事务写入，对账导出才有核销人。"""
    d = setup_(client, db)
    adm = db.query(Admin).filter_by(username="adm").first()
    r = client.post("/api/admin/orders/complete", json={"code": d["pickup_code"]})
    assert r.status_code == 200
    db.expire_all()  # expire_on_commit=False：setup_ 已把这单读进身份映射，刷掉旧值再断言
    o = db.get(Order, d["id"])
    assert o.status == "DONE" and o.done_at and o.verified_by == adm.id
    log = db.query(AdminLog).filter_by(action="complete", target=o.order_no).first()
    assert log is not None and log.admin_id == adm.id


def test_complete_pending_directly(client, db):
    """PENDING 直转 DONE：窗口场景货给了就完成，不强制先点备货。"""
    d = setup_(client, db, status="PENDING")
    r = client.post("/api/admin/orders/complete", json={"code": d["pickup_code"]})
    assert r.status_code == 200
    assert db.get(Order, d["id"]).status == "DONE"


def test_complete_twice_conflict(client, db):
    d = setup_(client, db, status="DONE")
    r = client.post("/api/admin/orders/complete", json={"code": d["pickup_code"]})
    assert r.status_code == 409 and "不能核销" in r.json()["detail"]


def test_complete_cancelled_conflict(client, db):
    d = setup_(client, db, status="CANCELLED")
    assert client.post("/api/admin/orders/complete",
                       json={"code": d["pickup_code"]}).status_code == 409


def test_unknown_code_404(client, db):
    setup_(client, db)
    assert client.post("/api/admin/orders/complete",
                       json={"code": "000001"}).status_code == 404
