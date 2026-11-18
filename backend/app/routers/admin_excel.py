from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Admin, AdminLog
from app.services.excel import (build_product_template, export_products_xlsx,
                                import_products_xlsx, workbook_response)

router = APIRouter(prefix="/api/admin/products", tags=["admin-excel"],
                   dependencies=[Depends(get_current_admin)])


@router.get("/template")
def template():
    return workbook_response(build_product_template(), "商品导入模板.xlsx")


@router.post("/import")
async def import_excel(file: UploadFile, db: Session = Depends(get_db),
                       admin: Admin = Depends(get_current_admin)):
    result = import_products_xlsx(db, file.file)
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="import",
                    target="products", detail=f"新增{result['created']} 更新{result['updated']}"))
    db.commit()
    return result


@router.get("/export")
def export(db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    db.add(AdminLog(admin_id=admin.id, username=admin.username, action="export",
                    target="products", detail="全量导出商品"))
    db.commit()
    return workbook_response(export_products_xlsx(db), "商品导出.xlsx")
