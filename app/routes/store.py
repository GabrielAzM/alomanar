from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import or_

from app.models import (
    AdminUser,
    URGENCY_SCORE,
    Occurrence,
    OccurrenceMapping,
    OccurrenceStatusHistory,
    OccurrenceUserMessage,
    Product,
    User,
    db,
)


store_bp = Blueprint("store", __name__)

CART_SESSION_KEY = "cart"
AUTO_COUPON_CODE = "ALOCLUB100"
USER_SESSION_KEY = "user_id"
ADMIN_SESSION_KEY = "admin_user_id"

CATEGORY_PAGE_COPY = {
    "kits": {
        "title": "Kits e acessorios",
        "subtitle": "Ferramentas praticas para montar uma rotina completa",
        "text": (
            "Selecao de pinceis, esponjas e combos para facilitar o dia a dia de quem "
            "gosta de maquiagem bem acabada com menos improviso."
        ),
        "image_filename": "img-categorias-acessorios-alomana.jpg",
    },
    "skincare": {
        "title": "Skincare",
        "subtitle": "Cuidado diario com texturas leves e produtos desejados",
        "text": (
            "Rotina com limpeza, hidratacao e protecao para preparar a pele e manter "
            "o viro saudavel em qualquer horario."
        ),
        "image_filename": "img-categorias-skincare-alomana.jpg",
    },
    "maquiagem": {
        "title": "Maquiagem",
        "subtitle": "Bases, olhos, labios e acabamento com cara de best-seller",
        "text": (
            "Vitrine com produtos que aparecem em listas de favoritos de quem procura "
            "boa performance, acabamento bonito e praticidade."
        ),
        "image_filename": "img-categorias-face-alomana.jpg",
    },
}

TESTIMONIALS = [
    {
        "name": "Yngrid",
        "photo": "img-clientes1-alomana.jpg",
        "text": "Encontrei varias marcas conhecidas e o checkout foi rapido, direto e facil de acompanhar.",
    },
    {
        "name": "Camilla",
        "photo": "img-clientes2-alomana.jpg",
        "text": "Gostei dos kits e da selecao de skincare. A navegacao passa mesmo cara de loja pronta.",
    },
    {
        "name": "Ana Caren",
        "photo": "img-clientes3-alomana.jpg",
        "text": "Os detalhes de produto e a organizacao por categoria deixaram a vitrine muito mais crivel.",
    },
    {
        "name": "Daviane",
        "photo": "img-clientes4-alomana.jpg",
        "text": "O cupom de lancamento no checkout fechou bem a experiencia e ficou coerente com campanha promocional.",
    },
]

HOME_BENEFITS = [
    {
        "title": "Marcas conhecidas",
        "text": "Curadoria com nomes lembrados em maquiagem, skincare e acessorios.",
    },
    {
        "title": "Cupom de estreia",
        "text": "Campanha promocional automatica para concluir o pedido sem atrito.",
    },
    {
        "title": "Acompanhamento online",
        "text": "Cada pedido gera protocolo e historico dentro da conta da cliente.",
    },
]

PRICE_FILTER_OPTIONS = (
    {"code": "todos", "label": "Todos os precos", "min_cents": None, "max_cents": None},
    {"code": "ate-99", "label": "Ate R$ 99", "min_cents": None, "max_cents": 9999},
    {"code": "100-179", "label": "R$ 100 a R$ 179", "min_cents": 10000, "max_cents": 17999},
    {"code": "180-249", "label": "R$ 180 a R$ 249", "min_cents": 18000, "max_cents": 24999},
    {"code": "250-ou-mais", "label": "Acima de R$ 250", "min_cents": 25000, "max_cents": None},
)

PRICE_FILTERS_BY_CODE = {item["code"]: item for item in PRICE_FILTER_OPTIONS}


def _sanitize_quantity(raw_quantity, default_value=1):
    try:
        qty = int(raw_quantity)
    except (TypeError, ValueError):
        return default_value
    return max(1, min(qty, 99))


def _normalize_digits(raw_value):
    return "".join(char for char in str(raw_value or "") if char.isdigit())


def _format_zip_code(raw_value):
    digits = _normalize_digits(raw_value)
    if len(digits) != 8:
        return (raw_value or "").strip()
    return f"{digits[:5]}-{digits[5:]}"


def _format_phone(raw_value):
    digits = _normalize_digits(raw_value)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return (raw_value or "").strip()


def _is_valid_email(value):
    cleaned = (value or "").strip()
    return "@" in cleaned and "." in cleaned.split("@")[-1]


def _get_cart_dict():
    raw_cart = session.get(CART_SESSION_KEY, {})
    if not isinstance(raw_cart, dict):
        raw_cart = {}

    cleaned_cart = {}
    for key, value in raw_cart.items():
        try:
            product_id = int(key)
            quantity = int(value)
        except (TypeError, ValueError):
            continue
        if quantity > 0:
            cleaned_cart[str(product_id)] = min(quantity, 99)

    if cleaned_cart != raw_cart:
        session[CART_SESSION_KEY] = cleaned_cart
        session.modified = True
    return cleaned_cart


def _save_cart(cart):
    session[CART_SESSION_KEY] = cart
    session.modified = True


def _build_cart_lines():
    cart = _get_cart_dict()
    if not cart:
        return [], 0

    product_ids = [int(product_id) for product_id in cart.keys()]
    products = Product.query.filter(Product.id.in_(product_ids), Product.active.is_(True)).all()
    products_map = {product.id: product for product in products}

    lines = []
    subtotal_cents = 0
    for product_id_str, quantity in cart.items():
        product = products_map.get(int(product_id_str))
        if not product:
            continue
        line_total_cents = product.price_cents * quantity
        subtotal_cents += line_total_cents
        lines.append(
            {
                "product": product,
                "quantity": quantity,
                "line_total_cents": line_total_cents,
            }
        )
    return lines, subtotal_cents


def _apply_ordering(query, order_code):
    if order_code == "menor-preco":
        return query.order_by(Product.price_cents.asc(), Product.id.asc())
    if order_code == "maior-preco":
        return query.order_by(Product.price_cents.desc(), Product.id.asc())
    if order_code == "mais-avaliados":
        return query.order_by(Product.rating.desc(), Product.review_count.desc(), Product.id.asc())
    return query.order_by(Product.featured_order.asc(), Product.id.asc())


def _normalize_price_filter(price_filter_code):
    normalized = (price_filter_code or "todos").strip().lower()
    return normalized if normalized in PRICE_FILTERS_BY_CODE else "todos"


def _apply_price_filter(query, price_filter_code):
    selected_filter = PRICE_FILTERS_BY_CODE.get(_normalize_price_filter(price_filter_code))
    if not selected_filter:
        return query

    min_cents = selected_filter["min_cents"]
    max_cents = selected_filter["max_cents"]

    if min_cents is not None:
        query = query.filter(Product.price_cents >= min_cents)
    if max_cents is not None:
        query = query.filter(Product.price_cents <= max_cents)
    return query


def _load_products(
    search_term="",
    category_slug="",
    order_code="mais-vendidos",
    price_filter_code="todos",
):
    query = Product.query.filter(Product.active.is_(True))

    if category_slug and category_slug != "todos":
        query = query.filter(Product.category_slug == category_slug)

    if search_term:
        like_term = f"%{search_term}%"
        query = query.filter(
            or_(
                Product.name.ilike(like_term),
                Product.brand.ilike(like_term),
                Product.subcategory_label.ilike(like_term),
                Product.description_short.ilike(like_term),
                Product.description_long.ilike(like_term),
            )
        )

    query = _apply_price_filter(query, price_filter_code)
    query = _apply_ordering(query, order_code)
    return query.all()


def _current_user():
    user_id = session.get(USER_SESSION_KEY)
    if not user_id:
        return None
    return db.session.get(User, user_id)


def _current_admin():
    admin_user_id = session.get(ADMIN_SESSION_KEY)
    if not admin_user_id:
        return None
    return db.session.get(AdminUser, admin_user_id)


def _build_checkout_form_data(user, source=None):
    source = source or {}
    return {
        "recipient_name": (source.get("recipient_name") or user.full_name or "").strip(),
        "contact_phone": _format_phone(source.get("contact_phone") or user.phone or ""),
        "contact_email": (source.get("contact_email") or user.email or "").strip().lower(),
        "zip_code": _format_zip_code(source.get("zip_code") or user.zip_code or ""),
        "street": (source.get("street") or user.street or "").strip(),
        "number": (source.get("number") or user.number or "").strip(),
        "complement": (source.get("complement") or user.complement or "").strip(),
        "neighborhood": (source.get("neighborhood") or user.neighborhood or "").strip(),
        "city": (source.get("city") or user.city or "").strip(),
        "state": (source.get("state") or user.state or "").strip().upper(),
        "delivery_window": (source.get("delivery_window") or "").strip(),
        "delivery_notes": (source.get("delivery_notes") or "").strip(),
        "observation": (source.get("observation") or "").strip(),
    }


def _validate_checkout_form(form_data):
    required_labels = {
        "recipient_name": "nome de recebimento",
        "zip_code": "CEP",
        "street": "rua",
        "number": "numero",
        "neighborhood": "bairro",
        "city": "cidade",
        "state": "UF",
    }

    errors = []
    for field_name, label in required_labels.items():
        if not form_data[field_name]:
            errors.append(f"Preencha {label}.")

    if form_data["recipient_name"] and len(form_data["recipient_name"]) < 5:
        errors.append("Informe um nome de recebimento mais completo.")

    if form_data["zip_code"] and len(_normalize_digits(form_data["zip_code"])) != 8:
        errors.append("Informe um CEP valido com 8 digitos.")

    phone_digits = _normalize_digits(form_data["contact_phone"])
    if phone_digits and len(phone_digits) not in (10, 11):
        errors.append("Informe um telefone valido com DDD.")

    if form_data["contact_email"] and not _is_valid_email(form_data["contact_email"]):
        errors.append("Informe um email valido para contato.")

    if form_data["state"] and len(form_data["state"]) != 2:
        errors.append("Informe a UF com 2 letras.")

    if len(form_data["delivery_notes"]) > 400:
        errors.append("As instrucoes de entrega devem ter no maximo 400 caracteres.")

    if len(form_data["observation"]) > 2000:
        errors.append("A observacao do pedido deve ter no maximo 2000 caracteres.")

    return errors


def _render_checkout(user, cart_lines, subtotal_cents, form_data=None):
    discount_cents = subtotal_cents
    total_cents = 0
    return render_template(
        "store/checkout.html",
        cart_lines=cart_lines,
        subtotal_cents=subtotal_cents,
        discount_cents=discount_cents,
        total_cents=total_cents,
        auto_coupon_code=AUTO_COUPON_CODE,
        user=user,
        checkout_data=form_data or _build_checkout_form_data(user),
        active_nav="checkout",
    )


@store_bp.route("/")
def home_page():
    featured_products = _load_products(order_code="mais-avaliados")[:6]
    return render_template(
        "store/home.html",
        featured_products=featured_products,
        testimonials=TESTIMONIALS,
        home_benefits=HOME_BENEFITS,
        active_nav="home",
    )


@store_bp.route("/produtos")
def products_page():
    search_term = request.args.get("q", "").strip()
    category_slug = request.args.get("categoria", "todos").strip().lower() or "todos"
    order_code = request.args.get("ordem", "mais-vendidos").strip().lower() or "mais-vendidos"
    price_filter_code = _normalize_price_filter(request.args.get("faixa_preco", "todos"))
    products = _load_products(
        search_term=search_term,
        category_slug=category_slug,
        order_code=order_code,
        price_filter_code=price_filter_code,
    )

    return render_template(
        "store/products.html",
        products=products,
        selected_category=category_slug,
        selected_order=order_code,
        selected_price_filter=price_filter_code,
        price_filter_options=PRICE_FILTER_OPTIONS,
        search_term=search_term,
        category_copy=CATEGORY_PAGE_COPY.get(category_slug),
        active_nav="produtos" if category_slug == "todos" else category_slug,
    )


@store_bp.route("/categoria/<slug>")
def category_page(slug):
    category_slug = slug.strip().lower()
    if category_slug not in CATEGORY_PAGE_COPY:
        abort(404)

    search_term = request.args.get("q", "").strip()
    order_code = request.args.get("ordem", "mais-vendidos").strip().lower() or "mais-vendidos"
    price_filter_code = _normalize_price_filter(request.args.get("faixa_preco", "todos"))
    products = _load_products(
        search_term=search_term,
        category_slug=category_slug,
        order_code=order_code,
        price_filter_code=price_filter_code,
    )

    return render_template(
        "store/products.html",
        products=products,
        selected_category=category_slug,
        selected_order=order_code,
        selected_price_filter=price_filter_code,
        price_filter_options=PRICE_FILTER_OPTIONS,
        search_term=search_term,
        category_copy=CATEGORY_PAGE_COPY[category_slug],
        active_nav=category_slug,
    )


@store_bp.route("/kits")
def kits_page():
    return redirect(url_for("store.category_page", slug="kits"))


@store_bp.route("/skincare")
def skincare_page():
    return redirect(url_for("store.category_page", slug="skincare"))


@store_bp.route("/maquiagem")
def maquiagem_page():
    return redirect(url_for("store.category_page", slug="maquiagem"))


@store_bp.route("/produto/<slug>")
def product_detail_page(slug):
    product = Product.query.filter_by(slug=slug, active=True).first_or_404()
    related_products = (
        Product.query.filter(
            Product.active.is_(True),
            Product.category_slug == product.category_slug,
            Product.id != product.id,
        )
        .order_by(Product.rating.desc(), Product.review_count.desc(), Product.id.asc())
        .limit(4)
        .all()
    )
    return render_template(
        "store/product_detail.html",
        product=product,
        related_products=related_products,
        active_nav=product.category_slug,
    )


@store_bp.route("/institucional")
def institutional_page():
    return render_template("store/institutional.html", active_nav="institucional")


@store_bp.route("/carrinho")
def cart_page():
    cart_lines, subtotal_cents = _build_cart_lines()
    return render_template(
        "store/cart.html",
        cart_lines=cart_lines,
        subtotal_cents=subtotal_cents,
        active_nav="carrinho",
    )


@store_bp.route("/saida-rapida")
def quick_exit():
    session.clear()
    return redirect(current_app.config.get("QUICK_EXIT_URL", "https://www.google.com/"))


@store_bp.route("/carrinho/item", methods=["POST"])
def add_cart_item():
    product_id = request.form.get("product_id", type=int)
    quantity = _sanitize_quantity(request.form.get("quantity", 1), default_value=1)
    redirect_to = request.form.get("next") or request.referrer or url_for("store.cart_page")

    product = Product.query.filter_by(id=product_id, active=True).first()
    if not product:
        flash("Produto nao encontrado.", "error")
        return redirect(redirect_to)

    cart = _get_cart_dict()
    current_quantity = cart.get(str(product.id), 0)
    cart[str(product.id)] = min(current_quantity + quantity, 99)
    _save_cart(cart)

    flash("Item adicionado ao carrinho.", "success")
    return redirect(redirect_to)


@store_bp.route("/carrinho/item/<int:item_id>/qtd", methods=["POST"])
def update_cart_item(item_id):
    redirect_to = request.form.get("next") or url_for("store.cart_page")
    cart = _get_cart_dict()
    key = str(item_id)
    if key not in cart:
        flash("Item nao encontrado no carrinho.", "error")
        return redirect(redirect_to)

    quantity = request.form.get("quantity", type=int)
    if quantity is None:
        action = request.form.get("action")
        if action == "inc":
            quantity = cart[key] + 1
        elif action == "dec":
            quantity = cart[key] - 1
        else:
            quantity = cart[key]

    if quantity <= 0:
        cart.pop(key, None)
    else:
        cart[key] = min(quantity, 99)

    _save_cart(cart)
    return redirect(redirect_to)


@store_bp.route("/carrinho/item/<int:item_id>/remover", methods=["POST"])
def remove_cart_item(item_id):
    redirect_to = request.form.get("next") or url_for("store.cart_page")
    cart = _get_cart_dict()
    cart.pop(str(item_id), None)
    _save_cart(cart)
    flash("Item removido do carrinho.", "success")
    return redirect(redirect_to)


@store_bp.route("/checkout")
def checkout_page():
    cart_lines, subtotal_cents = _build_cart_lines()
    if not cart_lines:
        flash("Seu carrinho esta vazio.", "warning")
        return redirect(url_for("store.products_page"))

    user = _current_user()
    admin_user = _current_admin()
    if admin_user and not user:
        flash(
            "Sessao admin ativa. O checkout funciona apenas para conta de usuaria.",
            "warning",
        )
        return redirect(url_for("admin.occurrences_page"))

    if not user:
        flash("Entre na sua conta para acompanhar o pedido.", "warning")
        return redirect(url_for("user.login_page", next=url_for("store.checkout_page")))

    return _render_checkout(user, cart_lines, subtotal_cents)


@store_bp.route("/checkout/finalizar", methods=["POST"])
def checkout_finalize():
    cart_lines, subtotal_cents = _build_cart_lines()
    if not cart_lines:
        flash("Seu carrinho esta vazio.", "warning")
        return redirect(url_for("store.products_page"))

    user = _current_user()
    admin_user = _current_admin()
    if admin_user and not user:
        flash(
            "Sessao admin ativa. Saia do perfil admin e entre como usuaria para finalizar.",
            "warning",
        )
        return redirect(url_for("admin.occurrences_page"))

    if not user:
        flash("Entre na sua conta para concluir o pedido.", "warning")
        return redirect(url_for("user.login_page", next=url_for("store.checkout_page")))

    form_data = _build_checkout_form_data(user, request.form)
    errors = _validate_checkout_form(form_data)
    if errors:
        for error_message in errors:
            flash(error_message, "error")
        return _render_checkout(user, cart_lines, subtotal_cents, form_data=form_data)

    product_ids = [line["product"].id for line in cart_lines]
    mappings = OccurrenceMapping.query.filter(OccurrenceMapping.product_id.in_(product_ids)).all()
    mappings_by_product_id = {mapping.product_id: mapping for mapping in mappings}

    categories = []
    highest_urgency = "Baixa"
    items_snapshot = []

    for line in cart_lines:
        product = line["product"]
        mapping = mappings_by_product_id.get(product.id)
        if mapping:
            categories.append(mapping.occurrence_category)
            mapping_urgency = (
                mapping.urgency_level if mapping.urgency_level in URGENCY_SCORE else "Baixa"
            )
            if URGENCY_SCORE[mapping_urgency] > URGENCY_SCORE[highest_urgency]:
                highest_urgency = mapping_urgency
        else:
            categories.append("Ocorrencia geral")

        items_snapshot.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "brand": product.brand,
                "subcategory_label": product.subcategory_label,
                "quantity": line["quantity"],
                "unit_price_cents": product.price_cents,
                "line_total_cents": line["line_total_cents"],
            }
        )

    mapped_category = ", ".join(list(dict.fromkeys(categories))) or "Ocorrencia geral"
    discount_cents = subtotal_cents
    total_cents = 0

    user.full_name = form_data["recipient_name"]
    user.phone = form_data["contact_phone"] or user.phone
    user.zip_code = form_data["zip_code"]
    user.street = form_data["street"]
    user.number = form_data["number"]
    user.complement = form_data["complement"] or None
    user.neighborhood = form_data["neighborhood"]
    user.city = form_data["city"]
    user.state = form_data["state"]

    occurrence = Occurrence(
        status="Novo",
        mapped_category=mapped_category,
        urgency_level=highest_urgency,
        user_id=user.id,
        recipient_name=form_data["recipient_name"],
        contact_phone=form_data["contact_phone"] or None,
        contact_email=form_data["contact_email"] or None,
        address_zip_code=form_data["zip_code"],
        address_street=form_data["street"],
        address_number=form_data["number"],
        address_complement=form_data["complement"] or None,
        address_neighborhood=form_data["neighborhood"],
        address_city=form_data["city"],
        address_state=form_data["state"],
        delivery_window=form_data["delivery_window"] or None,
        delivery_notes=form_data["delivery_notes"] or None,
        observation=form_data["observation"] or None,
        subtotal_cents=subtotal_cents,
        discount_cents=discount_cents,
        total_cents=total_cents,
    )
    occurrence.set_items(items_snapshot)
    db.session.add(occurrence)
    db.session.flush()

    db.session.add(
        OccurrenceStatusHistory(
            occurrence_id=occurrence.id,
            previous_status=None,
            new_status="Novo",
            changed_by_admin_id=None,
        )
    )

    if occurrence.observation:
        db.session.add(
            OccurrenceUserMessage(
                occurrence_id=occurrence.id,
                user_id=user.id,
                message_text=occurrence.observation,
            )
        )

    db.session.commit()

    _save_cart({})
    flash("Pedido finalizado com sucesso.", "success")
    return redirect(url_for("store.checkout_success_page", occurrence_id=occurrence.id))


@store_bp.route("/checkout/sucesso/<int:occurrence_id>")
def checkout_success_page(occurrence_id):
    occurrence = Occurrence.query.get_or_404(occurrence_id)
    user = _current_user()
    if not user or occurrence.user_id != user.id:
        flash("Acesso permitido apenas ao titular do pedido.", "error")
        return redirect(url_for("user.login_page", next=url_for("user.orders_page")))
    return render_template(
        "store/checkout_success.html",
        occurrence=occurrence,
        user=user,
        active_nav="checkout",
    )
