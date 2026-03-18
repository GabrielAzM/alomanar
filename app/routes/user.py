from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.models import Occurrence, OccurrenceUserMessage, User, db


user_bp = Blueprint("user", __name__)
USER_SESSION_KEY = "user_id"
ADMIN_SESSION_KEY = "admin_user_id"


def current_user():
    user_id = session.get(USER_SESSION_KEY)
    if not user_id:
        return None
    return db.session.get(User, user_id)


def user_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("user.login_page", next=request.path))
        g.user = user
        return view_func(*args, **kwargs)

    return wrapper


@user_bp.route("/cadastro", methods=["GET", "POST"])
def register_page():
    if current_user():
        return redirect(url_for("user.orders_page"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if len(full_name) < 5:
            flash("Informe seu nome completo.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        if len(username) < 3:
            flash("Informe um usuário com pelo menos 3 caracteres.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        if "@" not in email or "." not in email:
            flash("Informe um email válido.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        if len(password) < 6:
            flash("A senha deve ter no mínimo 6 caracteres.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        if password != confirm_password:
            flash("As senhas não coincidem.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        if User.query.filter_by(username=username).first():
            flash("Este nome de usuário já está em uso.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        if User.query.filter_by(email=email).first():
            flash("Este email já está cadastrado.", "error")
            return render_template("store/register.html", active_nav="cadastro")

        user = User(username=username, email=email, full_name=full_name, phone=phone or None)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session.pop(ADMIN_SESSION_KEY, None)
        session[USER_SESSION_KEY] = user.id
        session.modified = True
        flash("Cadastro realizado com sucesso.", "success")
        return redirect(url_for("user.orders_page"))

    return render_template("store/register.html", active_nav="cadastro")


@user_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user():
        return redirect(url_for("user.orders_page"))

    if request.method == "POST":
        login = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""
        next_path = request.args.get("next") or request.form.get("next") or ""
        admin_username = (current_app.config.get("ADMIN_DEFAULT_USERNAME", "admin") or "admin").strip()

        if login.lower() == admin_username.lower():
            flash("Use o acesso interno em /admin/login para entrar como admin.", "warning")
            return redirect(url_for("admin.login_page"))

        user = User.query.filter(
            (User.username == login) | (User.email == login.lower())
        ).first()
        if not user or not user.check_password(password):
            flash("Usuário/email ou senha inválidos.", "error")
            return render_template("store/login.html", active_nav="login")

        session.pop(ADMIN_SESSION_KEY, None)
        session[USER_SESSION_KEY] = user.id
        session.modified = True
        flash("Login realizado com sucesso.", "success")
        if next_path.startswith("/"):
            return redirect(next_path)
        return redirect(url_for("user.orders_page"))

    return render_template("store/login.html", active_nav="login")


@user_bp.route("/logout", methods=["POST"])
def logout():
    session.pop(USER_SESSION_KEY, None)
    session.modified = True
    flash("Sessão do usuário encerrada.", "success")
    return redirect(url_for("store.home_page"))


@user_bp.route("/meus-pedidos")
@user_required
def orders_page():
    orders = (
        Occurrence.query.filter_by(user_id=g.user.id)
        .order_by(Occurrence.created_at.desc())
        .all()
    )
    return render_template(
        "store/orders.html",
        orders=orders,
        user=g.user,
        active_nav="pedidos",
    )


@user_bp.route("/meus-pedidos/<int:occurrence_id>")
@user_required
def order_detail_page(occurrence_id):
    order = Occurrence.query.filter_by(id=occurrence_id, user_id=g.user.id).first_or_404()
    return render_template(
        "store/order_detail.html",
        order=order,
        active_nav="pedidos",
    )


@user_bp.route("/meus-pedidos/<int:occurrence_id>/mensagem", methods=["POST"])
@user_required
def order_add_message(occurrence_id):
    order = Occurrence.query.filter_by(id=occurrence_id, user_id=g.user.id).first_or_404()
    message_text = (request.form.get("message_text") or "").strip()
    if not message_text:
        flash("A mensagem não pode ser vazia.", "error")
        return redirect(url_for("user.order_detail_page", occurrence_id=order.id))

    if len(message_text) > 2000:
        flash("A mensagem deve ter no máximo 2000 caracteres.", "error")
        return redirect(url_for("user.order_detail_page", occurrence_id=order.id))

    message = OccurrenceUserMessage(
        occurrence_id=order.id,
        user_id=g.user.id,
        message_text=message_text,
    )
    db.session.add(message)
    db.session.commit()
    flash("Mensagem enviada para a equipe de atendimento.", "success")
    return redirect(url_for("user.order_detail_page", occurrence_id=order.id))
