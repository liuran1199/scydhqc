import io
import os
import zlib

from app.models import Admin
from app.utils.security import hash_password


def png_bytes(size_kb=1):
    return b"\x89PNG\r\n\x1a\n" + zlib.compress(b"0" * size_kb * 1024)


def admin_login(client, db, role="super"):
    db.add(Admin(username="adm", password_hash=hash_password("p"), role=role, name="管"))
    db.commit()
    client.post("/api/admin/auth/login", json={"username": "adm", "password": "p"})


def test_create_update_product(client, db):
    admin_login(client, db)
    r = client.post("/api/admin/products", json={
        "name": "测试米", "spec": "5kg", "unit": "袋",
        "price_original": 6750, "price_sale": 6620, "stock": 5})
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.put(f"/api/admin/products/{pid}", json={"price_sale": 6000, "status": "off"})
    assert r.json()["price_sale"] == 6000 and r.json()["status"] == "off"


def test_requires_admin(client, db):
    assert client.get("/api/admin/products").status_code == 401


def test_upload_rejects_txt_and_oversize(client, db, tmp_path):
    admin_login(client, db)
    r = client.post("/api/admin/upload",
                    files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")})
    assert r.status_code == 400
    big = b"\x89PNG\r\n\x1a\n" + os.urandom(6 * 1024 * 1024)  # >5MB，不可压缩
    r = client.post("/api/admin/upload",
                    files={"file": ("b.png", io.BytesIO(big), "image/png")})
    assert r.status_code == 400


def test_upload_png_ok(client, db, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))  # 不污染真实 uploads
    admin_login(client, db)
    r = client.post("/api/admin/upload",
                    files={"file": ("c.png", io.BytesIO(png_bytes()), "image/png")})
    assert r.status_code == 200
    assert r.json()["url"].startswith("/uploads/") and r.json()["url"].endswith(".png")


def test_category_crud(client, db):
    admin_login(client, db)
    cid = client.post("/api/admin/categories", json={"name": "蛋品"}).json()["id"]
    r = client.put(f"/api/admin/categories/{cid}", json={"name": "糖蜜蛋品", "enabled": True})
    assert r.json()["name"] == "糖蜜蛋品"


def test_update_product_writes_admin_log(client, db):
    """改价/改库存必须落操作日志（I-3，spec：改价需留痕）。"""
    from app.models import AdminLog
    admin_login(client, db)
    pid = client.post("/api/admin/products", json={
        "name": "日志米", "spec": "5kg", "unit": "袋",
        "price_original": 6750, "price_sale": 6620, "stock": 5}).json()["id"]
    client.put(f"/api/admin/products/{pid}", json={"price_sale": 6000})
    log = db.query(AdminLog).filter_by(action="product_update").first()
    assert log is not None and "price_sale" in log.detail and log.username == "adm"


def test_upload_rejects_fake_image_content(client, db, tmp_path, monkeypatch):
    """扩展名合法但内容不是图片 → 拒绝（I-6：仅扩展名校验可被绕过）。"""
    from app.config import settings
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    admin_login(client, db)
    r = client.post("/api/admin/upload",
                    files={"file": ("fake.png", io.BytesIO(b"not-a-png" * 64), "image/png")})
    assert r.status_code == 400


def test_upload_accepts_jpeg_magic(client, db, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    admin_login(client, db)
    r = client.post("/api/admin/upload",
                    files={"file": ("x.jpg", io.BytesIO(b"\xff\xd8\xff" + b"0" * 128), "image/jpeg")})
    assert r.status_code == 200 and r.json()["url"].endswith(".jpg")


# ── 商品多图：images 数组，第一张即封面 ──────────────────────────

def test_product_images_roundtrip(client, db):
    """创建带多图 → images 返回数组且 image 自动取第一张为封面"""
    admin_login(client, db)
    r = client.post("/api/admin/products", json={
        "name": "多图米", "spec": "5kg", "unit": "袋",
        "price_original": 6750, "price_sale": 6620,
        "images": ["/uploads/a.jpg", "/uploads/b.jpg", "/uploads/c.jpg"]})
    assert r.status_code == 200
    d = r.json()
    assert d["images"] == ["/uploads/a.jpg", "/uploads/b.jpg", "/uploads/c.jpg"]
    assert d["image"] == "/uploads/a.jpg"  # 封面 = 第一张


def test_product_images_update_syncs_cover(client, db):
    """更新 images 时封面同步；清空 images 封面也清空"""
    admin_login(client, db)
    pid = client.post("/api/admin/products", json={
        "name": "多图米", "price_original": 6750, "price_sale": 6620,
        "images": ["/uploads/a.jpg"]}).json()["id"]
    r = client.put(f"/api/admin/products/{pid}",
                   json={"images": ["/uploads/b.jpg", "/uploads/a.jpg"]})
    assert r.json()["image"] == "/uploads/b.jpg"
    assert r.json()["images"][0] == "/uploads/b.jpg"
    r = client.put(f"/api/admin/products/{pid}", json={"images": []})
    assert r.json()["image"] is None and r.json()["images"] == []


def test_product_images_validation(client, db):
    """非 /uploads/ 前缀的地址与超过 9 张均拒绝"""
    admin_login(client, db)
    r = client.post("/api/admin/products", json={
        "name": "坏图米", "price_original": 6750, "price_sale": 6620,
        "images": ["https://evil.example.com/x.jpg"]})
    assert r.status_code == 400
    r = client.post("/api/admin/products", json={
        "name": "太多图米", "price_original": 6750, "price_sale": 6620,
        "images": [f"/uploads/{i}.jpg" for i in range(10)]})
    assert r.status_code == 400


def test_public_detail_returns_images(client, db):
    """公开详情接口返回 images；仅存旧 image 字段的商品兜底为 [image]"""
    from app.models import Product
    admin_login(client, db)
    client.get("/api/auth/dev-login", params={"empid": "U901", "name": "图老师"})
    pid = client.post("/api/admin/products", json={
        "name": "公开米", "price_original": 6750, "price_sale": 6620,
        "images": ["/uploads/a.jpg", "/uploads/b.jpg"]}).json()["id"]
    d = client.get(f"/api/products/{pid}").json()
    assert d["images"] == ["/uploads/a.jpg", "/uploads/b.jpg"]
    # 旧数据兼容：只有 image 没有 images
    db.get(Product, pid).images = None
    db.commit()
    d = client.get(f"/api/products/{pid}").json()
    assert d["images"] == ["/uploads/a.jpg"]
