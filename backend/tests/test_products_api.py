from app.models import Category, Product


def seed_products(db):
    c = Category(name="调味酱料")
    db.add(c)
    db.flush()
    db.add_all([
        Product(name="海天黄豆酱", spec="800g", unit="瓶", price_original=1210,
                price_sale=1190, category_id=c.id, status="on", sort=1),
        Product(name="乌江榨菜", spec="60g", unit="袋", price_original=250,
                price_sale=250, status="on", sort=2),
        Product(name="下架品", spec="1kg", unit="瓶", price_original=1000,
                price_sale=900, status="off"),
    ])
    db.commit()


def login_teacher(client):
    client.get("/api/auth/dev-login?empid=T001&name=张老师")


def test_list_only_onshelf(client, db):
    seed_products(db)
    login_teacher(client)
    r = client.get("/api/products")
    assert r.status_code == 200
    names = [i["name"] for i in r.json()["items"]]
    assert names == ["海天黄豆酱", "乌江榨菜"]  # 下架品不可见，按 sort 排序


def test_category_filter_and_search(client, db):
    seed_products(db)
    login_teacher(client)
    cid = db.query(Category).first().id
    assert len(client.get(f"/api/products?category_id={cid}").json()["items"]) == 1
    assert client.get("/api/products?q=榨菜").json()["items"][0]["name"] == "乌江榨菜"


def test_detail_offshelf_404(client, db):
    seed_products(db)
    login_teacher(client)
    pid = db.query(Product).filter_by(name="下架品").first().id
    assert client.get(f"/api/products/{pid}").status_code == 404


def test_requires_login(client, db):
    assert client.get("/api/products").status_code == 401
