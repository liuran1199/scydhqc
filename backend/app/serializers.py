from app.models import Product


def product_to_dict(p: Product) -> dict:
    return {
        "id": p.id, "name": p.name, "brand": p.brand, "spec": p.spec,
        "unit": p.unit, "origin": p.origin,
        "price_original": p.price_original, "price_sale": p.price_sale,
        "image": p.image, "category_id": p.category_id, "status": p.status,
        "stock": p.stock, "sort": p.sort,
    }
