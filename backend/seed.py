"""初始化数据库：建表 + 导入商品 CSV。用法：DATABASE_URL=... python seed.py"""
import csv
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Category, Product


def import_products_csv(db: Session, path: str) -> dict:
    created = updated = 0
    cat_cache: dict[str, Category] = {}
    for row in csv.DictReader(open(path, encoding="utf-8")):
        cat_name = row["分类"].strip()
        if cat_name and cat_name not in cat_cache:
            c = db.query(Category).filter_by(name=cat_name).first()
            if not c:
                c = Category(name=cat_name, sort=len(cat_cache))
                db.add(c)
                db.flush()
            cat_cache[cat_name] = c
        name, spec = row["名称"].strip(), row["规格"].strip()
        p = db.query(Product).filter_by(name=name, spec=spec).first()
        fields = dict(
            category_id=cat_cache[cat_name].id if cat_name else None,
            unit=row["单位"].strip(),
            brand=row["品牌"].strip(),
            origin=row["产地"].strip(),
            price_original=int(round(float(row["原价元"]) * 100)),
            price_sale=int(round(float(row["售价元"]) * 100)),
            updated_at=datetime.now(),
        )
        if p:
            for k, v in fields.items():
                setattr(p, k, v)
            updated += 1
        else:
            db.add(Product(name=name, spec=spec, status="on", stock=None, **fields))
            created += 1
    db.commit()
    return {"created": created, "updated": updated, "categories": len(cat_cache)}


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    result = import_products_csv(SessionLocal(), "seed_data/products_initial.csv")
    print(result)
