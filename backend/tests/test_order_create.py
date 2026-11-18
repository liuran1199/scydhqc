from app.models import Category, Order, Product


def seed(db, stock=None):
    c = Category(name="粮油米面")
    db.add(c)
    db.flush()
    p1 = Product(name="五常大米", spec="5kg", unit="袋", price_original=6750,
                 price_sale=6620, category_id=c.id, status="on", stock=stock)
    p2 = Product(name="豆油", spec="5升", unit="桶", price_original=5610,
                 price_sale=5500, category_id=c.id, status="on")
    db.add_all([p1, p2])
    db.commit()
    return p1, p2


def test_create_order_price_from_server_and_snapshot(client, db):
    p1, p2 = seed(db)
    client.get("/api/auth/dev-login?empid=T001&name=张老师")
    r = client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 2}, {"product_id": p2.id, "qty": 1}],
        "remark": "周五取",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 6620 * 2 + 5500      # 服务端按 DB 价计算
    assert len(d["items"]) == 2
    item = d["items"][0]
    assert item["p_name"] == "五常大米" and item["p_price"] == 6620  # 快照
    assert len(d["pickup_code"]) == 6 and d["pickup_code"].isdigit()
    assert d["order_no"].startswith("20")     # YYYYMMDD-NNNNNN
    assert d["status"] == "PENDING"


def test_offshelf_rejected(client, db):
    p1, _ = seed(db)
    p1.status = "off"
    db.commit()
    client.get("/api/auth/dev-login?empid=T001")
    r = client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 1}]})
    assert r.status_code == 400 and "下架" in r.json()["detail"]


def test_stock_insufficient(client, db):
    p1, _ = seed(db, stock=2)
    client.get("/api/auth/dev-login?empid=T001")
    r = client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 3}]})
    assert r.status_code == 400 and "库存" in r.json()["detail"]
    assert db.query(Order).count() == 0       # 未生成订单


def test_stock_deducted_and_null_unlimited(client, db):
    p1, p2 = seed(db, stock=10)
    client.get("/api/auth/dev-login?empid=T001")
    client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 3},
                                                {"product_id": p2.id, "qty": 99}]})
    db.expire_all()
    assert db.get(Product, p1.id).stock == 7  # 扣减
    assert db.get(Product, p2.id).stock is None  # NULL 无限不动


def test_invalid_qty_rejected(client, db):
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    assert client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 0}]}).status_code == 400


def test_rate_limited(client, db):
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    codes = [client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 1}]}).status_code for _ in range(11)]
    assert codes.count(429) == 1              # 第 11 次 429


def test_pickup_code_unique(client, db):
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    client.get("/api/auth/dev-login?empid=T002")
    client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 1}]})
    client.post("/api/orders", json={"items": [{"product_id": p1.id, "qty": 1}]})
    codes = [o.pickup_code for o in db.query(Order).all()]
    assert len(set(codes)) == 2


def test_order_rejects_stale_cart_price(client, db):
    """购物车旧价 ≠ 当前售价 → 409 提示重新确认（I-7：改价后静默按新价成交不可接受）。"""
    p1, _ = seed(db)
    client.get("/api/auth/dev-login?empid=T001")
    r = client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 1, "price_sale": 5000}]})  # 加购时的旧价
    assert r.status_code == 409 and "重新确认" in r.json()["detail"]
    # 带当前价（用户已在确认页看到新价）正常成交
    r2 = client.post("/api/orders", json={
        "items": [{"product_id": p1.id, "qty": 1, "price_sale": 6620}]})
    assert r2.status_code == 200 and r2.json()["total"] == 6620
