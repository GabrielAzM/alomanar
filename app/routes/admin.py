from collections import Counter
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import case, or_

from app.models import (
    AdminUser,
    Occurrence,
    OccurrenceMapping,
    OccurrenceNote,
    OccurrenceStatusHistory,
    OccurrenceUserMessage,
    Product,
    URGENCY_SCORE,
    User,
    VALID_OCCURRENCE_STATUSES,
    VALID_URGENCY_LEVELS,
    db,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_SESSION_KEY = "admin_user_id"
USER_SESSION_KEY = "user_id"
PENDING_STATUS_FILTER = "pendentes"
STATUS_FILTER_OPTIONS = (
    (PENDING_STATUS_FILTER, "Em analise / pendentes"),
    *[(status, status) for status in VALID_OCCURRENCE_STATUSES],
)
STATUS_SORT_ORDER = {
    "Novo": 1,
    "Em triagem": 2,
    "Encaminhado": 3,
    "Concluido": 4,
}
OCCURRENCE_SORT_OPTIONS = (
    ("mais-recentes", "Mais recentes"),
    ("mais-antigos", "Mais antigos"),
    ("urgencia", "Maior urgencia"),
    ("atualizados", "Atualizados recentemente"),
    ("status", "Status de atendimento"),
    ("protocolo", "Protocolo mais novo"),
)
VALID_OCCURRENCE_SORT_CODES = {code for code, _label in OCCURRENCE_SORT_OPTIONS}


def _current_admin():
    admin_user_id = session.get(ADMIN_SESSION_KEY)
    if not admin_user_id:
        return None
    return db.session.get(AdminUser, admin_user_id)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        admin_user = _current_admin()
        if not admin_user:
            next_path = request.path
            return redirect(url_for("admin.login_page", next=next_path))
        g.admin_user = admin_user
        return view_func(*args, **kwargs)

    return wrapper


def _apply_occurrence_sorting(query, sort_code):
    urgency_rank = case(URGENCY_SCORE, value=Occurrence.urgency_level, else_=0)
    status_rank = case(STATUS_SORT_ORDER, value=Occurrence.status, else_=99)

    if sort_code == "mais-antigos":
        return query.order_by(Occurrence.created_at.asc(), Occurrence.id.asc())
    if sort_code == "urgencia":
        return query.order_by(
            urgency_rank.desc(),
            Occurrence.updated_at.desc(),
            Occurrence.created_at.desc(),
        )
    if sort_code == "atualizados":
        return query.order_by(Occurrence.updated_at.desc(), Occurrence.created_at.desc())
    if sort_code == "status":
        return query.order_by(
            status_rank.asc(),
            urgency_rank.desc(),
            Occurrence.updated_at.desc(),
            Occurrence.created_at.desc(),
        )
    if sort_code == "protocolo":
        return query.order_by(Occurrence.id.desc())
    return query.order_by(Occurrence.created_at.desc(), Occurrence.id.desc())


@admin_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if _current_admin():
        return redirect(url_for("admin.occurrences_page"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        next_path = request.args.get("next") or request.form.get("next") or ""

        admin_user = AdminUser.query.filter_by(username=username).first()
        if admin_user and admin_user.check_password(password):
            session.pop(USER_SESSION_KEY, None)
            session[ADMIN_SESSION_KEY] = admin_user.id
            session.modified = True
            flash("Login realizado com sucesso.", "success")

            if next_path.startswith("/"):
                return redirect(next_path)
            return redirect(url_for("admin.occurrences_page"))

        flash("Usuario ou senha invalidos.", "error")

    return render_template("admin/login.html", active_nav="admin-login")


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.pop(ADMIN_SESSION_KEY, None)
    session.modified = True
    flash("Sessao encerrada.", "success")
    return redirect(url_for("admin.login_page"))


@admin_bp.route("/ocorrencias")
@admin_required
def occurrences_page():
    status_filter = (request.args.get("status") or "").strip()
    urgency_filter = (request.args.get("urgencia") or "").strip()
    category_filter = (request.args.get("categoria") or "").strip()
    sort_by = (request.args.get("ordem") or "mais-recentes").strip()
    search_term = (request.args.get("q") or "").strip()
    if sort_by not in VALID_OCCURRENCE_SORT_CODES:
        sort_by = "mais-recentes"

    query = Occurrence.query.outerjoin(User, Occurrence.user_id == User.id)
    category_options = [
        item[0]
        for item in db.session.query(Occurrence.mapped_category)
        .filter(Occurrence.mapped_category.isnot(None))
        .distinct()
        .order_by(Occurrence.mapped_category.asc())
        .all()
        if item[0]
    ]

    if status_filter == PENDING_STATUS_FILTER:
        query = query.filter(Occurrence.status.in_(("Novo", "Em triagem")))
    elif status_filter in VALID_OCCURRENCE_STATUSES:
        query = query.filter(Occurrence.status == status_filter)
    else:
        status_filter = ""

    if urgency_filter in VALID_URGENCY_LEVELS:
        query = query.filter(Occurrence.urgency_level == urgency_filter)
    else:
        urgency_filter = ""

    if category_filter in category_options:
        query = query.filter(Occurrence.mapped_category == category_filter)
    else:
        category_filter = ""

    if search_term:
        if search_term.isdigit():
            query = query.filter(Occurrence.id == int(search_term))
        else:
            like_term = f"%{search_term}%"
            query = query.filter(
                or_(
                    Occurrence.mapped_category.ilike(like_term),
                    Occurrence.recipient_name.ilike(like_term),
                    Occurrence.contact_phone.ilike(like_term),
                    Occurrence.contact_email.ilike(like_term),
                    Occurrence.address_street.ilike(like_term),
                    Occurrence.address_city.ilike(like_term),
                    Occurrence.observation.ilike(like_term),
                    Occurrence.delivery_notes.ilike(like_term),
                    Occurrence.user_messages.any(
                        OccurrenceUserMessage.message_text.ilike(like_term)
                    ),
                    User.username.ilike(like_term),
                    User.email.ilike(like_term),
                )
            )

    occurrences = _apply_occurrence_sorting(query, sort_by).all()
    status_counts = Counter(occurrence.status for occurrence in occurrences)
    high_priority_count = sum(
        1 for occurrence in occurrences if occurrence.urgency_level in ("Alta", "Critica")
    )
    summary_cards = (
        {"label": "Casos visiveis", "value": len(occurrences), "tone": "default"},
        {
            "label": "Em analise",
            "value": status_counts["Novo"] + status_counts["Em triagem"],
            "tone": "warning",
        },
        {
            "label": "Encaminhados",
            "value": status_counts["Encaminhado"],
            "tone": "info",
        },
        {
            "label": "Concluidos",
            "value": status_counts["Concluido"],
            "tone": "success",
        },
        {
            "label": "Alta ou critica",
            "value": high_priority_count,
            "tone": "danger",
        },
    )
    return render_template(
        "admin/occurrences.html",
        occurrences=occurrences,
        status_filter=status_filter,
        status_filter_options=STATUS_FILTER_OPTIONS,
        urgency_filter=urgency_filter,
        urgency_levels=VALID_URGENCY_LEVELS,
        category_filter=category_filter,
        category_options=category_options,
        sort_by=sort_by,
        sort_options=OCCURRENCE_SORT_OPTIONS,
        search_term=search_term,
        summary_cards=summary_cards,
        result_count=len(occurrences),
        statuses=VALID_OCCURRENCE_STATUSES,
        active_nav="admin-occurrences",
        admin_user=g.admin_user,
    )


@admin_bp.route("/ocorrencias/<int:occurrence_id>")
@admin_required
def occurrence_detail_page(occurrence_id):
    occurrence = Occurrence.query.get_or_404(occurrence_id)
    return render_template(
        "admin/occurrence_detail.html",
        occurrence=occurrence,
        statuses=VALID_OCCURRENCE_STATUSES,
        active_nav="admin-occurrences",
        admin_user=g.admin_user,
    )


@admin_bp.route("/ocorrencias/<int:occurrence_id>/status", methods=["POST"])
@admin_required
def occurrence_status_update(occurrence_id):
    occurrence = Occurrence.query.get_or_404(occurrence_id)
    new_status = (request.form.get("status") or "").strip()
    if new_status not in VALID_OCCURRENCE_STATUSES:
        flash("Status invalido.", "error")
        return redirect(url_for("admin.occurrence_detail_page", occurrence_id=occurrence_id))

    if occurrence.status != new_status:
        previous_status = occurrence.status
        occurrence.status = new_status
        occurrence.updated_at = datetime.utcnow()
        db.session.add(
            OccurrenceStatusHistory(
                occurrence_id=occurrence.id,
                changed_by_admin_id=g.admin_user.id,
                previous_status=previous_status,
                new_status=new_status,
            )
        )
        db.session.commit()
        flash("Status atualizado.", "success")
    else:
        flash("Status mantido sem alteracoes.", "warning")

    return redirect(url_for("admin.occurrence_detail_page", occurrence_id=occurrence_id))


@admin_bp.route("/ocorrencias/<int:occurrence_id>/nota", methods=["POST"])
@admin_required
def occurrence_add_note(occurrence_id):
    occurrence = Occurrence.query.get_or_404(occurrence_id)
    note_text = (request.form.get("note_text") or "").strip()
    if not note_text:
        flash("A nota nao pode ser vazia.", "error")
        return redirect(url_for("admin.occurrence_detail_page", occurrence_id=occurrence.id))

    note = OccurrenceNote(
        occurrence_id=occurrence.id,
        admin_user_id=g.admin_user.id,
        note_text=note_text,
    )
    db.session.add(note)
    db.session.commit()
    flash("Nota interna registrada.", "success")
    return redirect(url_for("admin.occurrence_detail_page", occurrence_id=occurrence.id))


@admin_bp.route("/mapeamentos", methods=["GET", "POST"])
@admin_required
def mappings_page():
    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        occurrence_category = (request.form.get("occurrence_category") or "").strip()
        urgency_level = (request.form.get("urgency_level") or "").strip()

        if not product_id or not occurrence_category:
            flash("Produto e categoria sao obrigatorios.", "error")
            return redirect(url_for("admin.mappings_page"))

        if urgency_level not in VALID_URGENCY_LEVELS:
            urgency_level = "Baixa"

        product = db.session.get(Product, product_id)
        if not product:
            flash("Produto nao encontrado.", "error")
            return redirect(url_for("admin.mappings_page"))

        mapping = OccurrenceMapping.query.filter_by(product_id=product.id).first()
        if not mapping:
            mapping = OccurrenceMapping(product_id=product.id)
            db.session.add(mapping)

        mapping.occurrence_category = occurrence_category
        mapping.urgency_level = urgency_level
        db.session.commit()
        flash("Mapeamento atualizado.", "success")
        return redirect(url_for("admin.mappings_page"))

    products = Product.query.filter(Product.active.is_(True)).order_by(
        Product.category_slug.asc(), Product.name.asc()
    )
    return render_template(
        "admin/mappings.html",
        products=products,
        urgency_levels=VALID_URGENCY_LEVELS,
        active_nav="admin-mappings",
        admin_user=g.admin_user,
    )
