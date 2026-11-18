from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.exceptions import AppError
from app.models import Category, Product
from app.serializers import product_to_dict

router = APIRouter(prefix="/api", tags=["products"], dependencies=[Depends(get_current_user)])


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.query(Category).filter_by(enabled=True).order_by(Category.sort, Category.id).all()
    return [{"id": c.id, "name": c.name} for c in rows]


@router.get("/products")
def list_products(category_id: int | None = None, q: str | None = None,
                  page: int = Query(1, ge=1),
                  db: Session = Depends(get_db)):
    query = db.query(Product).filter(Product.status == "on")
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if q:
        query = query.filter(Product.name.contains(q))
    total = query.count()
    rows = (query.order_by(Product.sort, Product.id)
            .offset((page - 1) * 20).limit(20).all())
    return {"items": [product_to_dict(p) for p in rows], "total": total, "page": page}


@router.get("/products/{pid}")
def product_detail(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p or p.status != "on":
        raise AppError(404, "商品不存在或已下架")
    return product_to_dict(p)
