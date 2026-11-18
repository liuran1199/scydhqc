import os
import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_admin
from app.exceptions import AppError
from app.models import Admin, AdminLog, Category, Product
from app.serializers import product_to_dict

router = APIRouter(prefix="/api/admin", tags=["admin-products"],
                   dependencies=[Depends(get_current_admin)])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD = 5 * 1024 * 1024


class ProductIn(BaseModel):
    name: str
    spec: str = ""
    unit: str = "件"
    brand: str = ""
    origin: str = ""
    category_id: int | None = None
    price_original: int
    price_sale: int
    stock: int | None = None
    sort: int = 0
    status: str = "on"
    image: str | None = None


class ProductUpdateIn(BaseModel):
    name: str | None = None
    spec: str | None = None
    unit: str | None = None
    brand: str | None = None
    origin: str | None = None
    category_id: int | None = None
    price_original: int | None = None
    price_sale: int | None = None
    stock: int | None = None
    sort: int | None = None
    status: str | None = None
    image: str | None = None


def _validate(data: dict) -> None:
    if "price_sale" in data and data["price_sale"] is not None and data["price_sale"] <= 0:
        raise AppError(400, "售价必须大于 0（单位：分）")
    if "price_original" in data and data["price_original"] is not None and data["price_original"] <= 0:
        raise AppError(400, "原价必须大于 0（单位：分）")
    if data.get("status") is not None and data["status"] not in ("on", "off"):
        raise AppError(400, "status 只能是 on/off")
    if "stock" in data and data["stock"] is not None and data["stock"] < 0:
        raise AppError(400, "库存不能为负")


@router.get("/products")
def admin_products(q: str | None = None, category_id: int | None = None,
                   status: str | None = None, page: int = Query(1, ge=1),
                   db: Session = Depends(get_db)):
    query = db.query(Product)
    if q:
        query = query.filter(Product.name.contains(q))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if status:
        query = query.filter(Product.status == status)
    total = query.count()
    rows = (query.order_by(Product.sort, Product.id)
            .offset((page - 1) * 20).limit(20).all())
    return {"items": [product_to_dict(p) for p in rows], "total": total, "page": page}


@router.post("/products")
def create_product(body: ProductIn, db: Session = Depends(get_db)):
    _validate(body.model_dump())
    p = Product(**body.model_dump())
    db.add(p)
    db.commit()
    return product_to_dict(p)


@router.put("/products/{pid}")
def update_product(pid: int, body: ProductUpdateIn, db: Session = Depends(get_db),
                   admin: Admin = Depends(get_current_admin)):
    p = db.get(Product, pid)
    if not p:
        raise AppError(404, "商品不存在")
    data = body.model_dump(exclude_unset=True)  # 部分更新：任意字段
    _validate(data)
    changes = [f"{k} {getattr(p, k)}→{v}"
               for k, v in data.items() if getattr(p, k) != v]
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    if changes:  # 改价/改库存等留痕
        db.add(AdminLog(admin_id=admin.id, username=admin.username,
                        action="product_update", target=p.name,
                        detail="；".join(changes)))
        db.commit()
    return product_to_dict(p)


class CategoryIn(BaseModel):
    name: str
    sort: int = 0
    enabled: bool = True


@router.get("/categories")
def admin_categories(db: Session = Depends(get_db)):
    rows = db.query(Category).order_by(Category.sort, Category.id).all()
    return [{"id": c.id, "name": c.name, "sort": c.sort, "enabled": c.enabled}
            for c in rows]


@router.post("/categories")
def create_category(body: CategoryIn, db: Session = Depends(get_db)):
    if db.query(Category).filter_by(name=body.name).first():
        raise AppError(400, "分类已存在")
    c = Category(**body.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id, "name": c.name, "sort": c.sort, "enabled": c.enabled}


@router.put("/categories/{cid}")
def update_category(cid: int, body: CategoryIn, db: Session = Depends(get_db)):
    c = db.get(Category, cid)
    if not c:
        raise AppError(404, "分类不存在")
    c.name, c.sort, c.enabled = body.name, body.sort, body.enabled
    db.commit()
    return {"id": c.id, "name": c.name, "sort": c.sort, "enabled": c.enabled}


def _is_image(data: bytes) -> bool:
    """文件头魔数校验：扩展名可伪造，内容骗不了人。"""
    if data[:3] == b"\xff\xd8\xff":
        return True  # JPEG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True  # PNG
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True  # WebP
    return False


@router.post("/upload")
async def upload(file: UploadFile):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise AppError(400, "仅支持 jpg/png/webp 图片")
    data = await file.read(MAX_UPLOAD + 1)  # 只读到上限+1，超大文件不整读进内存
    if len(data) > MAX_UPLOAD:
        raise AppError(400, "图片不能超过 5MB")
    if not _is_image(data):
        raise AppError(400, "文件内容不是有效的图片")
    os.makedirs(settings.upload_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.upload_dir, name), "wb") as f:
        f.write(data)
    return {"url": f"/uploads/{name}"}
