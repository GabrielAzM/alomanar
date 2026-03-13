from flask import Flask, session

from config import Config

from .models import AdminUser, User, db, migrate_schema, seed_database
from .routes.admin import admin_bp
from .routes.api import api_bp
from .routes.store import _build_cart_lines, store_bp
from .routes.user import user_bp
from .utils import format_brl, format_datetime_br


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    app.register_blueprint(store_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(user_bp)

    app.jinja_env.filters["brl"] = format_brl
    app.jinja_env.filters["datetime_br"] = format_datetime_br

    @app.context_processor
    def inject_global_vars():
        cart = session.get("cart", {})
        if isinstance(cart, dict):
            cart_count = sum(int(quantity) for quantity in cart.values() if str(quantity).isdigit())
        else:
            cart_count = 0
        cart_preview_lines, cart_subtotal_cents = _build_cart_lines()

        user_id = session.get("user_id")
        current_user = db.session.get(User, user_id) if user_id else None
        admin_user_id = session.get("admin_user_id")
        current_admin = db.session.get(AdminUser, admin_user_id) if admin_user_id else None
        return {
            "cart_items_count": cart_count,
            "cart_preview_lines": cart_preview_lines,
            "cart_subtotal_cents": cart_subtotal_cents,
            "current_user": current_user,
            "current_admin": current_admin,
        }

    with app.app_context():
        db.create_all()
        migrate_schema()
        seed_database(app.config)

    return app
