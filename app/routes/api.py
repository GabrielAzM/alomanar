from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app.models import Product


api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.get("/health")
def healthcheck():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat() + "Z"})


@api_bp.get("/produtos")
def list_products():
    search_term = (request.args.get("q") or "").strip()
    query = Product.query.filter(Product.active.is_(True))

    if search_term:
        like_term = f"%{search_term}%"
        query = query.filter(
            or_(Product.name.ilike(like_term), Product.description_short.ilike(like_term))
        )

    products = query.order_by(Product.featured_order.asc(), Product.id.asc()).all()
    payload = [
        {
            "id": product.id,
            "slug": product.slug,
            "name": product.name,
            "brand": product.brand,
            "category": product.category_slug,
            "subcategory": product.subcategory_label,
            "price_cents": product.price_cents,
            "image": product.image_filename,
            "rating": product.rating,
            "review_count": product.review_count,
        }
        for product in products
    ]
    return jsonify(payload)
