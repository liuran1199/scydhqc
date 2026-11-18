from io import BytesIO

from openpyxl import Workbook, load_workbook
from sqlalchemy.orm import Session

from app.models import Category, Product

HEADERS = ["商品名称", "规格", "单位", "品牌", "产地", "分类",
           "原价(元)", "售价(元)", "库存(空=无限)", "排序"]


def _to_cents(v) -> int | None:
    if v is None or v == "":
        return None
    return int(round(float(v) * 100))


def build_product_template() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "商品导入"
    ws.append(HEADERS)
    return wb


def import_products_xlsx(db: Session, fileobj) -> dict:
    wb = load_workbook(fileobj, data_only=True)
    ws = wb.active
    created = updated = 0
    errors: list[dict] = []
    cats: dict[str, int] = {}
    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue
        try:
            # 先解析全部字段（任何解析错误都在动库之前抛出）
            name = str(row[0] or "").strip()
            spec = str(row[1] or "").strip()
            if not name:
                raise ValueError("商品名称不能为空")
            po, ps = _to_cents(row[6]), _to_cents(row[7])
            if po is None or ps is None:
                raise ValueError("原价/售价必须为数字")
            stock = None if row[8] in (None, "") else int(row[8])
            sort = int(row[9]) if row[9] not in (None, "") else 0
            cat_name = str(row[5] or "").strip()
            # 再做库操作
            cat_id = None
            if cat_name:
                if cat_name not in cats:
                    c = db.query(Category).filter_by(name=cat_name).first()
                    if not c:
                        c = Category(name=cat_name, sort=99)
                        db.add(c)
                        db.flush()
                    cats[cat_name] = c.id
                cat_id = cats[cat_name]
            p = db.query(Product).filter_by(name=name, spec=spec).first()
            fields = dict(unit=str(row[2] or "件"), brand=str(row[3] or ""),
                          origin=str(row[4] or ""), category_id=cat_id,
                          price_original=po, price_sale=ps, stock=stock,
                          sort=sort)
            if p:
                for k, v in fields.items():
                    setattr(p, k, v)
                updated += 1
            else:
                db.add(Product(name=name, spec=spec, status="on", **fields))
                created += 1
            db.commit()  # 逐行提交：坏行回滚不影响已导入的好行
        except Exception as e:  # 行级错误不阻断整体
            db.rollback()
            errors.append({"row": i, "msg": str(e)})
    return {"created": created, "updated": updated, "errors": errors}


def export_products_xlsx(db: Session) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "商品"
    ws.append(HEADERS + ["状态", "id"])
    for p in db.query(Product).order_by(Product.sort, Product.id).all():
        ws.append([p.name, p.spec, p.unit, p.brand, p.origin,
                   p.category.name if p.category_id else "",
                   p.price_original / 100, p.price_sale / 100,
                   "" if p.stock is None else p.stock, p.sort,
                   "在售" if p.status == "on" else "下架", p.id])
    return wb


def workbook_response(wb: Workbook, filename: str):
    from urllib.parse import quote

    from fastapi.responses import StreamingResponse
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    # RFC 5987：中文文件名需 filename* 编码（HTTP 头是 latin-1）
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
