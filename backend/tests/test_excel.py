import io

from openpyxl import Workbook

from app.models import Admin, Product
from app.utils.security import hash_password


def admin_login(client, db):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role="super"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def xlsx_file(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["商品名称", "规格", "单位", "品牌", "产地", "分类",
               "原价(元)", "售价(元)", "库存(空=无限)", "排序"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_template_download(client, db):
    admin_login(client, db)
    r = client.get("/api/admin/products/template")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]


def test_import_creates_and_reports_errors(client, db):
    admin_login(client, db)
    buf = xlsx_file([
        ["新米", "5kg", "袋", "", "", "粮油米面", 67.5, 66.2, "", 1],   # OK
        ["", "1kg", "瓶", "", "", "", 10, 9, "", ""],                  # 缺名称
        ["坏价", "1kg", "瓶", "", "", "", "abc", 9, "", ""],           # 价格非数字
    ])
    r = client.post("/api/admin/products/import",
                    files={"file": ("import.xlsx", buf,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    d = r.json()
    assert d["created"] == 1
    assert len(d["errors"]) == 2
    assert d["errors"][0]["row"] == 3            # Excel 行号（含表头）
    assert db.query(Product).filter_by(name="新米").count() == 1


def test_import_updates_by_name_spec(client, db):
    admin_login(client, db)
    db.add(Product(name="新米", spec="5kg", unit="袋", price_original=6750,
                   price_sale=6620))
    db.commit()
    buf = xlsx_file([["新米", "5kg", "袋", "", "", "", 67.5, 60.0, 8, ""]])
    d = client.post("/api/admin/products/import",
                    files={"file": ("i.xlsx", buf,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert d["updated"] == 1 and d["created"] == 0
    p = db.query(Product).filter_by(name="新米").first()
    assert p.price_sale == 6000 and p.stock == 8


def test_export_contains_all(client, db):
    admin_login(client, db)
    db.add(Product(name="米A", spec="1kg", unit="袋", price_original=100, price_sale=90))
    db.commit()
    r = client.get("/api/admin/products/export")
    assert r.status_code == 200 and len(r.content) > 500


def test_export_writes_admin_log(client, db):
    """商品全量导出必须落操作日志（I-3）。"""
    from app.models import AdminLog
    admin_login(client, db)
    assert client.get("/api/admin/products/export").status_code == 200
    log = db.query(AdminLog).filter_by(action="export").first()
    assert log is not None and log.target == "products"
