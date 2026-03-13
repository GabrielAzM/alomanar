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
from sqlalchemy import or_

from app.models import (
    AdminUser,
    Occurrence,
    OccurrenceMapping,
    OccurrenceNote,
    OccurrenceStatusHistory,
    Product,
    User,
    VALID_OCCURRENCE_STATUSES,
    VALID_URGENCY_LEVELS,
    db,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_SESSION_KEY = "admin_user_id"


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
            session[ADMIN_SESSION_KEY] = admin_user.id
            session.modified = True
            flash("Login realizado com sucesso.", "success")

            if next_path.startswith("/"):
                return redirect(next_path)
            return redirect(url_for("admin.occurrences_page"))

        flash("Usuario ou senha invalidos.", "error")

    return render_template("admin/login.html", active_nav="admin")


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
    search_term = (request.args.get("q") or "").strip()

    query = Occurrence.query.outerjoin(User, Occurrence.user_id == User.id)

    if status_filter in VALID_OCCURRENCE_STATUSES:
        query = query.filter(Occurrence.status == status_filter)

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
                    User.username.ilike(like_term),
                    User.email.ilike(like_term),
                )
            )

    occurrences = query.order_by(Occurrence.created_at.desc()).all()
    return render_template(
        "admin/occurrences.html",
        occurrences=occurrences,
        status_filter=status_filter,
        search_term=search_term,
        statuses=VALID_OCCURRENCE_STATUSES,
        active_nav="admin",
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
        active_nav="admin",
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
        active_nav="admin",
        admin_user=g.admin_user,
    )
