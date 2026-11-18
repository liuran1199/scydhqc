from app.models import Category, Product
from seed import import_products_csv


def test_seed_imports_66_products(db):
    result = import_products_csv(db, "seed_data/products_initial.csv")
    assert result["created"] == 66
    assert db.query(Product).count() == 66
    assert db.query(Category).count() == 5
    p = db.query(Product).filter_by(name="味好美番茄沙司").first()
    assert p.price_original == 780 and p.price_sale == 770  # 分
    assert p.spec == "330g" and p.unit == "袋" and p.status == "on"
    assert p.stock is None  # 无限
    egg = db.query(Product).filter_by(name="柴鸡蛋").first()
    assert egg.price_sale == 13000
