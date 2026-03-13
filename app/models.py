import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()

VALID_URGENCY_LEVELS = ("Baixa", "Media", "Alta", "Critica")
VALID_OCCURRENCE_STATUSES = ("Novo", "Em triagem", "Encaminhado", "Concluido")
URGENCY_SCORE = {"Baixa": 1, "Media": 2, "Alta": 3, "Critica": 4}


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    brand = db.Column(db.String(120), nullable=False, default="AloMana")
    category_slug = db.Column(db.String(40), nullable=False, index=True)
    category_label = db.Column(db.String(80), nullable=False)
    subcategory_label = db.Column(db.String(80), nullable=False, default="Produto")
    price_cents = db.Column(db.Integer, nullable=False)
    description_short = db.Column(db.Text, nullable=False)
    description_long = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255), nullable=False)
    badge_label = db.Column(db.String(80), nullable=True)
    shade_label = db.Column(db.String(120), nullable=True)
    size_label = db.Column(db.String(80), nullable=True)
    highlights_json = db.Column(db.Text, nullable=False, default="[]")
    rating = db.Column(db.Float, nullable=False, default=4.8)
    review_count = db.Column(db.Integer, nullable=False, default=0)
    featured_order = db.Column(db.Integer, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    mapping = db.relationship(
        "OccurrenceMapping",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def set_highlights(self, highlights):
        self.highlights_json = json.dumps(highlights or [], ensure_ascii=False)

    def get_highlights(self):
        try:
            payload = json.loads(self.highlights_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(payload, list):
            return []
        return [str(item).strip() for item in payload if str(item).strip()]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    zip_code = db.Column(db.String(16), nullable=True)
    street = db.Column(db.String(160), nullable=True)
    number = db.Column(db.String(20), nullable=True)
    complement = db.Column(db.String(120), nullable=True)
    neighborhood = db.Column(db.String(120), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(2), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    occurrences = db.relationship(
        "Occurrence",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Occurrence.created_at)",
    )
    messages = db.relationship(
        "OccurrenceUserMessage",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(OccurrenceUserMessage.created_at)",
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def has_saved_address(self):
        return bool(
            self.zip_code
            and self.street
            and self.number
            and self.neighborhood
            and self.city
            and self.state
        )

    @property
    def address_line(self):
        if not self.has_saved_address:
            return ""
        parts = [self.street, self.number]
        if self.complement:
            parts.append(self.complement)
        return ", ".join(part for part in parts if part)

    @property
    def city_line(self):
        first = self.neighborhood or ""
        rest = " / ".join(part for part in [self.city, self.state] if part)
        if first and rest:
            return f"{first} - {rest}"
        return first or rest


class OccurrenceMapping(db.Model):
    __tablename__ = "occurrence_mappings"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False, unique=True, index=True
    )
    occurrence_category = db.Column(db.String(120), nullable=False)
    urgency_level = db.Column(db.String(20), nullable=False, default="Baixa")

    product = db.relationship("Product", back_populates="mapping")


class Occurrence(db.Model):
    __tablename__ = "occurrences"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    status = db.Column(db.String(30), nullable=False, default="Novo", index=True)
    mapped_category = db.Column(db.String(255), nullable=False)
    urgency_level = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    recipient_name = db.Column(db.String(160), nullable=True)
    contact_phone = db.Column(db.String(40), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    address_zip_code = db.Column(db.String(16), nullable=True)
    address_street = db.Column(db.String(160), nullable=True)
    address_number = db.Column(db.String(20), nullable=True)
    address_complement = db.Column(db.String(120), nullable=True)
    address_neighborhood = db.Column(db.String(120), nullable=True)
    address_city = db.Column(db.String(120), nullable=True)
    address_state = db.Column(db.String(2), nullable=True)
    delivery_window = db.Column(db.String(120), nullable=True)
    delivery_notes = db.Column(db.Text, nullable=True)
    observation = db.Column(db.Text, nullable=True)

    items_json = db.Column(db.Text, nullable=False, default="[]")
    subtotal_cents = db.Column(db.Integer, nullable=False, default=0)
    discount_cents = db.Column(db.Integer, nullable=False, default=0)
    total_cents = db.Column(db.Integer, nullable=False, default=0)

    notes = db.relationship(
        "OccurrenceNote",
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="desc(OccurrenceNote.created_at)",
    )
    user_messages = db.relationship(
        "OccurrenceUserMessage",
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="desc(OccurrenceUserMessage.created_at)",
    )
    histories = db.relationship(
        "OccurrenceStatusHistory",
        back_populates="occurrence",
        cascade="all, delete-orphan",
        order_by="desc(OccurrenceStatusHistory.changed_at)",
    )
    user = db.relationship("User", back_populates="occurrences")

    def set_items(self, items):
        self.items_json = json.dumps(items, ensure_ascii=False)

    def get_items(self):
        try:
            payload = json.loads(self.items_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(payload, list):
            return []
        return payload

    @property
    def address_line(self):
        parts = [self.address_street, self.address_number]
        if self.address_complement:
            parts.append(self.address_complement)
        return ", ".join(part for part in parts if part)

    @property
    def city_line(self):
        first = self.address_neighborhood or ""
        rest = " / ".join(part for part in [self.address_city, self.address_state] if part)
        if first and rest:
            return f"{first} - {rest}"
        return first or rest


class OccurrenceNote(db.Model):
    __tablename__ = "occurrence_notes"

    id = db.Column(db.Integer, primary_key=True)
    occurrence_id = db.Column(
        db.Integer, db.ForeignKey("occurrences.id"), nullable=False, index=True
    )
    admin_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    note_text = db.Column(db.Text, nullable=False)

    occurrence = db.relationship("Occurrence", back_populates="notes")
    admin_user = db.relationship("AdminUser", back_populates="notes")


class OccurrenceUserMessage(db.Model):
    __tablename__ = "occurrence_user_messages"

    id = db.Column(db.Integer, primary_key=True)
    occurrence_id = db.Column(
        db.Integer, db.ForeignKey("occurrences.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    message_text = db.Column(db.Text, nullable=False)

    occurrence = db.relationship("Occurrence", back_populates="user_messages")
    user = db.relationship("User", back_populates="messages")


class OccurrenceStatusHistory(db.Model):
    __tablename__ = "occurrence_status_history"

    id = db.Column(db.Integer, primary_key=True)
    occurrence_id = db.Column(
        db.Integer, db.ForeignKey("occurrences.id"), nullable=False, index=True
    )
    changed_by_admin_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True
    )
    previous_status = db.Column(db.String(30), nullable=True)
    new_status = db.Column(db.String(30), nullable=False)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    occurrence = db.relationship("Occurrence", back_populates="histories")
    changed_by = db.relationship("AdminUser", back_populates="status_changes")


class AdminUser(db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    notes = db.relationship("OccurrenceNote", back_populates="admin_user")
    status_changes = db.relationship("OccurrenceStatusHistory", back_populates="changed_by")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


def _product_payload(
    *,
    slug,
    name,
    brand,
    category_slug,
    category_label,
    subcategory_label,
    price_cents,
    description_short,
    description_long,
    image_filename,
    featured_order,
    badge_label=None,
    shade_label=None,
    size_label=None,
    rating=4.8,
    review_count=0,
    highlights=None,
):
    return {
        "slug": slug,
        "name": name,
        "brand": brand,
        "category_slug": category_slug,
        "category_label": category_label,
        "subcategory_label": subcategory_label,
        "price_cents": price_cents,
        "description_short": description_short,
        "description_long": description_long,
        "image_filename": image_filename,
        "badge_label": badge_label,
        "shade_label": shade_label,
        "size_label": size_label,
        "rating": rating,
        "review_count": review_count,
        "featured_order": featured_order,
        "active": True,
        "highlights": highlights or [],
    }


DEFAULT_PRODUCTS = [
    _product_payload(
        slug="reveal-the-real-12hr-foundation",
        name="Base Liquida Reveal The Real 12H",
        brand="Sephora Collection",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Base",
        price_cents=11900,
        description_short="Base de cobertura media com acabamento natural e longa duracao.",
        description_long=(
            "Formula leve que uniformiza a pele, segura bem ao longo do dia e entrega "
            "acabamento confortavel para rotina, eventos e maquiagem social."
        ),
        image_filename="img-produtos-base-alomana.jpg",
        featured_order=1,
        badge_label="Best-seller",
        shade_label="30N",
        size_label="30 ml",
        rating=4.8,
        review_count=312,
        highlights=["Cobertura media", "Acabamento natural", "Longa duracao"],
    ),
    _product_payload(
        slug="best-skin-ever-foundation",
        name="Base Liquida Best Skin Ever",
        brand="Sephora Collection",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Base",
        price_cents=13900,
        description_short="Cobertura construivel com textura fina e viro acetinado.",
        description_long=(
            "Ideal para quem quer pele corrigida com aspecto fresco. A textura espalha "
            "facil, aceita camadas e funciona bem com acabamento glow ou matte."
        ),
        image_filename="img-produtos-base-alomana.jpg",
        featured_order=2,
        badge_label="Lancamento",
        shade_label="22.5Y",
        size_label="30 ml",
        rating=4.7,
        review_count=248,
        highlights=["Cobertura construivel", "Toque macio", "Boa fixacao"],
    ),
    _product_payload(
        slug="niina-secrets-hidra-glow-base",
        name="Base Niina Secrets Hidra Glow",
        brand="Eudora",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Base",
        price_cents=6990,
        description_short="Base glow com hidratacao e cobertura leve a media.",
        description_long=(
            "Entrega luminosidade elegante, boa aderencia e sensacao confortavel para "
            "quem busca viro saudavel e acabamento de pele bem cuidada."
        ),
        image_filename="img-produtos-base-alomana.jpg",
        featured_order=3,
        badge_label="Glow favorito",
        shade_label="Bege 30",
        size_label="30 ml",
        rating=4.6,
        review_count=521,
        highlights=["Hidratacao", "Glow natural", "Cobertura leve a media"],
    ),
    _product_payload(
        slug="radiant-creamy-concealer",
        name="Corretivo Radiant Creamy Concealer",
        brand="NARS",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Corretivo",
        price_cents=19900,
        description_short="Corretivo cremoso de alta cobertura com viro iluminado.",
        description_long=(
            "Conhecido por uniformizar olheiras com acabamento sofisticado, sem marcar "
            "demais a regiao. Funciona tanto em pontos localizados quanto no rosto todo."
        ),
        image_filename="img-produtos-corretivos-alomana.jpg",
        featured_order=4,
        badge_label="Iconico",
        shade_label="Custard",
        size_label="6 ml",
        rating=4.9,
        review_count=810,
        highlights=["Alta cobertura", "Textura cremosa", "Acabamento luminoso"],
    ),
    _product_payload(
        slug="radiant-creamy-concealer-mini",
        name="Corretivo Radiant Creamy Concealer Mini",
        brand="NARS",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Corretivo",
        price_cents=10900,
        description_short="Versao compacta do corretivo queridinho para levar na necessaire.",
        description_long=(
            "Perfeito para retoques, viagens e testes de tonalidade. Mantem a mesma "
            "cobertura cremosa da versao tradicional em formato mais pratico."
        ),
        image_filename="img-produtos-corretivos-alomana.jpg",
        featured_order=5,
        badge_label="Mini size",
        shade_label="Vanilla",
        size_label="1.4 ml",
        rating=4.8,
        review_count=215,
        highlights=["Formato pratico", "Retoque rapido", "Alta cobertura"],
    ),
    _product_payload(
        slug="soft-pinch-liquid-blush-mini",
        name="Blush Liquido Soft Pinch Mini",
        brand="Rare Beauty",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Blush",
        price_cents=14900,
        description_short="Blush liquido pigmentado com acabamento fresco e facil de esfumar.",
        description_long=(
            "Bastam poucos pontos para um efeito corado elegante. A textura liquida "
            "espalha bem e permite desde um rubor suave ate um look mais marcante."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=6,
        badge_label="Mini favorito",
        shade_label="Hope",
        size_label="3.2 ml",
        rating=4.9,
        review_count=432,
        highlights=["Alta pigmentacao", "Esfuma facil", "Acabamento natural"],
    ),
    _product_payload(
        slug="soft-pinch-luminous-powder-blush",
        name="Blush em Po Soft Pinch Luminous",
        brand="Rare Beauty",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Blush em po",
        price_cents=19900,
        description_short="Blush em po com brilho sutil e acabamento aveludado.",
        description_long=(
            "Combina cor uniforme com luminosidade delicada para valorizar a pele sem "
            "pesar. Boa escolha para makes sociais e acabamento sofisticado."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=7,
        badge_label="Glow suave",
        shade_label="Joy",
        size_label="2.8 g",
        rating=4.8,
        review_count=188,
        highlights=["Toque aveludado", "Brilho discreto", "Cor uniforme"],
    ),
    _product_payload(
        slug="soft-pinch-liquid-contour",
        name="Contorno Liquido Soft Pinch",
        brand="Rare Beauty",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Contorno",
        price_cents=17900,
        description_short="Contorno liquido de facil espalhabilidade e acabamento natural.",
        description_long=(
            "Desenha o rosto com leveza e sem manchas, funcionando bem tanto com base "
            "leve quanto em peles mais preparadas para maquiagem completa."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=8,
        badge_label="Queridinho",
        shade_label="Happy Sol",
        size_label="11 ml",
        rating=4.7,
        review_count=164,
        highlights=["Facil de esfumar", "Nao marca", "Acabamento leve"],
    ),
    _product_payload(
        slug="cream-lip-stain",
        name="Batom Liquido Cream Lip Stain",
        brand="Sephora Collection",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Batom liquido",
        price_cents=6900,
        description_short="Batom liquido matte com cor intensa e longa duracao.",
        description_long=(
            "A cobertura aparece ja na primeira camada e seca com conforto. Ideal para "
            "quem quer cor vibrante, boa duracao e acabamento uniforme."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=9,
        badge_label="Matte classico",
        shade_label="13 Marvelous Mauve",
        size_label="5 ml",
        rating=4.7,
        review_count=574,
        highlights=["Alta pigmentacao", "Viro matte", "Longa duracao"],
    ),
    _product_payload(
        slug="the-colossal-waterproof",
        name="Mascara de Cilios The Colossal Waterproof",
        brand="Maybelline NY",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Mascara de cilios",
        price_cents=7990,
        description_short="Mascara a prova d'agua para volume e definicao no dia a dia.",
        description_long=(
            "Escovinha encorpada que separa e entrega volume perceptivel com formula "
            "resistente a umidade, calor e rotina prolongada."
        ),
        image_filename="img-produtos-rimel-alomana.jpg",
        featured_order=10,
        badge_label="A prova d'agua",
        size_label="9.2 ml",
        rating=4.6,
        review_count=690,
        highlights=["Volume", "Resistencia a agua", "Aplicacao uniforme"],
    ),
    _product_payload(
        slug="the-falsies-lash-lift",
        name="Mascara de Cilios The Falsies Lash Lift",
        brand="Maybelline NY",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Mascara de cilios",
        price_cents=9490,
        description_short="Efeito lifting nos cilios com curvatura e alongamento visivel.",
        description_long=(
            "A escova de dupla curvatura ajuda a levantar os fios desde a raiz, criando "
            "resultado de cilios curvados e bem definidos sem pesar."
        ),
        image_filename="img-produtos-rimel-alomana.jpg",
        featured_order=11,
        badge_label="Lifting instantaneo",
        size_label="9.6 ml",
        rating=4.7,
        review_count=401,
        highlights=["Curvatura", "Alongamento", "Boa separacao"],
    ),
    _product_payload(
        slug="natural-eyes-palette",
        name="Paleta Natural Eyes",
        brand="Too Faced",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Paleta de sombras",
        price_cents=28900,
        description_short="Paleta neutra com acabamentos matte e cintilante para varias ocasioes.",
        description_long=(
            "Reune tons classicos para looks sutis, maquiagem de trabalho e producoes "
            "mais elaboradas. Boa pigmentacao e combinacoes faceis de usar."
        ),
        image_filename="img-produtos-paletaDeSombra-alomana.jpg",
        featured_order=12,
        badge_label="Paleta neutra",
        size_label="17.1 g",
        rating=4.8,
        review_count=137,
        highlights=["Tons versateis", "Matte e brilho", "Boa pigmentacao"],
    ),
    _product_payload(
        slug="photo-finish-smooth-blur-primer",
        name="Primer Photo Finish Smooth & Blur",
        brand="Smashbox",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Primer",
        price_cents=15900,
        description_short="Primer siliconado que suaviza textura e prepara a pele.",
        description_long=(
            "Ajuda a deixar a maquiagem mais uniforme, reduzindo a aparencia de poros e "
            "criando base macia para base, corretivo e produtos em po."
        ),
        image_filename="img-produtos-base-alomana.jpg",
        featured_order=13,
        badge_label="Prep de pele",
        size_label="12 ml",
        rating=4.7,
        review_count=203,
        highlights=["Suaviza poros", "Toque sedoso", "Melhora a duracao"],
    ),
    _product_payload(
        slug="translucent-loose-setting-powder",
        name="Po Solto Translucent Loose Setting Powder",
        brand="Laura Mercier",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Po solto",
        price_cents=29900,
        description_short="Po solto translucido com acabamento leve e sofisticado.",
        description_long=(
            "Controla brilho sem comprometer o acabamento da pele. Conhecido pela textura "
            "fina e pela capacidade de selar a maquiagem com elegancia."
        ),
        image_filename="img-produtos-corretivos-alomana.jpg",
        featured_order=14,
        badge_label="Acabamento profissional",
        size_label="29 g",
        rating=4.9,
        review_count=344,
        highlights=["Textura fina", "Controla brilho", "Nao pesa"],
    ),
    _product_payload(
        slug="all-nighter-setting-spray",
        name="Spray Fixador All Nighter",
        brand="Urban Decay",
        category_slug="maquiagem",
        category_label="Maquiagem",
        subcategory_label="Fixador",
        price_cents=21900,
        description_short="Spray fixador para prolongar a maquiagem por muitas horas.",
        description_long=(
            "Ajuda a manter a producao mais integra ao longo do dia e da noite, com "
            "nevoa fina e sensacao leve depois da aplicacao."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=15,
        badge_label="Fixacao prolongada",
        size_label="118 ml",
        rating=4.8,
        review_count=286,
        highlights=["Bruma fina", "Boa duracao", "Acabamento leve"],
    ),
    _product_payload(
        slug="lip-sleeping-mask",
        name="Mascara Labial Lip Sleeping Mask",
        brand="Laneige",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Mascara labial",
        price_cents=15900,
        description_short="Tratamento noturno para labios macios, nutridos e com viro bonito.",
        description_long=(
            "Textura rica e confortavel para usar antes de dormir ou como balm mais "
            "encorpado durante o dia. Ajuda a recuperar ressecamento rapidamente."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=16,
        badge_label="Skincare hit",
        shade_label="Berry",
        size_label="20 g",
        rating=4.9,
        review_count=612,
        highlights=["Nutre profundamente", "Maciez rapida", "Uso noturno"],
    ),
    _product_payload(
        slug="total-cleansr-remove-it-all",
        name="Gel de Limpeza Total Cleans'r Remove-It-All",
        brand="Fenty Skin",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Gel de limpeza",
        price_cents=19900,
        description_short="Gel cremoso de limpeza que remove impurezas e oleosidade.",
        description_long=(
            "Limpa sem ressecar, deixa sensacao de pele fresca e prepara bem para as "
            "proximas etapas da rotina, da hidratacao ao protetor."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=17,
        badge_label="Limpeza diaria",
        size_label="145 ml",
        rating=4.7,
        review_count=148,
        highlights=["Limpa sem repuxar", "Espuma cremosa", "Uso diario"],
    ),
    _product_payload(
        slug="watermelon-glow-pha-bha-toner",
        name="Tonico Watermelon Glow PHA+BHA",
        brand="Glow Recipe",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Tonico",
        price_cents=24900,
        description_short="Tonico hidratante com textura leve e viro luminoso.",
        description_long=(
            "Combina esfoliacao suave com sensacao fresca e ajuda a deixar a pele mais "
            "uniforme, macia e preparada para receber os tratamentos seguintes."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=18,
        badge_label="Glow routine",
        size_label="150 ml",
        rating=4.8,
        review_count=119,
        highlights=["Esfoliacao suave", "Luminosidade", "Toque hidratante"],
    ),
    _product_payload(
        slug="watermelon-glow-hue-drops",
        name="Serum Glow Watermelon Hue Drops",
        brand="Glow Recipe",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Serum glow",
        price_cents=22900,
        description_short="Serum iluminador que mistura tratamento e efeito bronzeado suave.",
        description_long=(
            "Pode ser usado sozinho ou misturado ao hidratante para adicionar viro "
            "radiante e tom dourado discreto sem pesar na pele."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=19,
        badge_label="Glow bronzeado",
        size_label="40 ml",
        rating=4.7,
        review_count=103,
        highlights=["Ilumina", "Tom gradual", "Textura leve"],
    ),
    _product_payload(
        slug="dew-balm-spf45",
        name="Bastao Dew Balm Watermelon Niacinamide SPF 45",
        brand="Glow Recipe",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Protetor solar",
        price_cents=21900,
        description_short="Bastao facial com protecao solar e brilho viroso.",
        description_long=(
            "Formato pratico para reaplicar ao longo do dia, com acabamento luminoso e "
            "sensacao confortavel para usar por cima ou sem maquiagem."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=20,
        badge_label="Protecao pratica",
        size_label="16.5 g",
        rating=4.6,
        review_count=92,
        highlights=["SPF 45", "Reaplicacao facil", "Acabamento glow"],
    ),
    _product_payload(
        slug="lait-creme-concentre",
        name="Creme Hidratante Lait-Creme Concentre",
        brand="Embryolisse",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Hidratante facial",
        price_cents=15900,
        description_short="Creme hidratante classico com textura rica e multifuncional.",
        description_long=(
            "Vai bem como hidratante, primer hidratante e reforco de conforto em areas "
            "mais secas. Um dos produtos mais lembrados em kits de maquiagem profissional."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=21,
        badge_label="Cult classic",
        size_label="75 ml",
        rating=4.8,
        review_count=267,
        highlights=["Hidrata", "Prepara a pele", "Multifuncional"],
    ),
    _product_payload(
        slug="urban-environment-oil-free-spf30",
        name="Protetor Solar Urban Environment Oil-Free SPF 30",
        brand="Shiseido",
        category_slug="skincare",
        category_label="Skincare",
        subcategory_label="Protetor solar",
        price_cents=22900,
        description_short="Protetor facial leve com toque seco e boa aderencia.",
        description_long=(
            "Ideal para pele mista a oleosa, com formula fluida que protege no dia a dia "
            "e funciona bem antes da maquiagem."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=22,
        badge_label="Toque seco",
        size_label="30 ml",
        rating=4.7,
        review_count=131,
        highlights=["Protecao diaria", "Textura leve", "Boa aderencia"],
    ),
    _product_payload(
        slug="everyday-essentials-kit",
        name="Kit Everyday Essentials",
        brand="Real Techniques",
        category_slug="kits",
        category_label="Kits e Acessorios",
        subcategory_label="Kit de pinceis",
        price_cents=13900,
        description_short="Kit com pinceis e esponja para uma necessaire pratica.",
        description_long=(
            "Seleciona ferramentas coringa para pele e acabamento, com formato pensado "
            "para facilitar a rotina de quem quer montar um kit eficiente."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=23,
        badge_label="Kit essencial",
        size_label="5 pecas",
        rating=4.8,
        review_count=226,
        highlights=["Kit completo", "Uso diario", "Ferramentas versateis"],
    ),
    _product_payload(
        slug="miracle-complexion-sponge",
        name="Esponja Miracle Complexion",
        brand="Real Techniques",
        category_slug="kits",
        category_label="Kits e Acessorios",
        subcategory_label="Esponja",
        price_cents=7900,
        description_short="Esponja de maquiagem para acabamento polido e aplicacao uniforme.",
        description_long=(
            "O formato em varias faces ajuda na aplicacao de base, corretivo e contorno, "
            "criando acabamento bonito sem exigir muita habilidade."
        ),
        image_filename="img-produtos-alomana.jpg",
        featured_order=24,
        badge_label="Acessorio favorito",
        size_label="1 unidade",
        rating=4.7,
        review_count=331,
        highlights=["Acabamento uniforme", "Facil de usar", "Versatil"],
    ),
]

for default_product in DEFAULT_PRODUCTS:
    default_product["image_filename"] = f"products/{default_product['slug']}.svg"

LEGACY_DEFAULT_PRODUCT_SLUGS = {
    "corretivo-colorido-4-seasons",
    "base-liquida-second-skin",
    "paleta-behind-the-scenes",
    "mascara-speak-volume",
    "kit-mae-e-filha",
    "kit-pinceis-precisao",
    "gel-limpeza-purify-reset",
    "protetor-barreira-invisivel",
}

DEFAULT_PRODUCT_MAPPINGS = {
    "reveal-the-real-12hr-foundation": ("Violencia fisica", "Alta"),
    "best-skin-ever-foundation": ("Violencia psicologica", "Media"),
    "niina-secrets-hidra-glow-base": ("Violencia moral", "Baixa"),
    "radiant-creamy-concealer": ("Ameaca imediata", "Critica"),
    "radiant-creamy-concealer-mini": ("Assedio", "Media"),
    "soft-pinch-liquid-blush-mini": ("Coacao", "Media"),
    "soft-pinch-luminous-powder-blush": ("Acompanhamento continuo", "Baixa"),
    "soft-pinch-liquid-contour": ("Perseguicao", "Alta"),
    "cream-lip-stain": ("Violencia patrimonial", "Media"),
    "the-colossal-waterproof": ("Ameaca imediata", "Critica"),
    "the-falsies-lash-lift": ("Assedio", "Media"),
    "natural-eyes-palette": ("Violencia psicologica", "Alta"),
    "photo-finish-smooth-blur-primer": ("Violencia moral", "Baixa"),
    "translucent-loose-setting-powder": ("Coacao", "Alta"),
    "all-nighter-setting-spray": ("Risco familiar", "Alta"),
    "lip-sleeping-mask": ("Acompanhamento continuo", "Baixa"),
    "total-cleansr-remove-it-all": ("Necessidade de acolhimento", "Alta"),
    "watermelon-glow-pha-bha-toner": ("Violencia moral", "Baixa"),
    "watermelon-glow-hue-drops": ("Acompanhamento continuo", "Baixa"),
    "dew-balm-spf45": ("Monitoramento de risco", "Media"),
    "lait-creme-concentre": ("Necessidade de acolhimento", "Media"),
    "urban-environment-oil-free-spf30": ("Monitoramento de risco", "Baixa"),
    "everyday-essentials-kit": ("Risco familiar", "Alta"),
    "miracle-complexion-sponge": ("Ocorrencia geral", "Baixa"),
}


def seed_database(app_config):
    existing_products = {item.slug: item for item in Product.query.all()}
    default_slugs = {item["slug"] for item in DEFAULT_PRODUCTS}

    for product_payload in DEFAULT_PRODUCTS:
        payload = dict(product_payload)
        highlights = payload.pop("highlights", [])
        product = existing_products.get(payload["slug"])

        if product is None:
            product = Product(**payload)
            db.session.add(product)
        else:
            for field_name, value in payload.items():
                setattr(product, field_name, value)

        product.set_highlights(highlights)

    for legacy_slug in LEGACY_DEFAULT_PRODUCT_SLUGS:
        legacy_product = existing_products.get(legacy_slug)
        if legacy_product and legacy_slug not in default_slugs:
            legacy_product.active = False

    db.session.commit()

    all_products = {item.slug: item for item in Product.query.all()}
    for slug, product in all_products.items():
        default_category, default_urgency = DEFAULT_PRODUCT_MAPPINGS.get(
            slug, ("Ocorrencia geral", "Baixa")
        )
        mapping = OccurrenceMapping.query.filter_by(product_id=product.id).first()
        if mapping is None:
            db.session.add(
                OccurrenceMapping(
                    product_id=product.id,
                    occurrence_category=default_category,
                    urgency_level=default_urgency,
                )
            )
            continue

        if not mapping.occurrence_category:
            mapping.occurrence_category = default_category
        if mapping.urgency_level not in VALID_URGENCY_LEVELS:
            mapping.urgency_level = default_urgency

    admin_username = app_config.get("ADMIN_DEFAULT_USERNAME", "admin")
    admin_user = AdminUser.query.filter_by(username=admin_username).first()
    if admin_user is None and not AdminUser.query.first():
        admin_user = AdminUser(username=admin_username)
        admin_user.set_password(app_config.get("ADMIN_DEFAULT_PASSWORD", "admin123"))
        db.session.add(admin_user)

    demo_username = app_config.get("USER_DEFAULT_USERNAME", "usuario_demo")
    demo_email = app_config.get("USER_DEFAULT_EMAIL", "usuario@alomana.local")
    demo_user = User.query.filter_by(username=demo_username).first()
    if demo_user is None and not User.query.first():
        demo_user = User(
            username=demo_username,
            email=demo_email,
            full_name="Cliente Demo AloMana",
            phone="(11) 99876-5432",
            zip_code="01311-000",
            street="Avenida Paulista",
            number="900",
            complement="Apto 42",
            neighborhood="Bela Vista",
            city="Sao Paulo",
            state="SP",
        )
        demo_user.set_password(app_config.get("USER_DEFAULT_PASSWORD", "usuario123"))
        db.session.add(demo_user)
    elif demo_user is not None:
        demo_user.email = demo_email
        demo_user.full_name = demo_user.full_name or "Cliente Demo AloMana"
        demo_user.phone = demo_user.phone or "(11) 99876-5432"
        demo_user.zip_code = demo_user.zip_code or "01311-000"
        demo_user.street = demo_user.street or "Avenida Paulista"
        demo_user.number = demo_user.number or "900"
        demo_user.complement = demo_user.complement or "Apto 42"
        demo_user.neighborhood = demo_user.neighborhood or "Bela Vista"
        demo_user.city = demo_user.city or "Sao Paulo"
        demo_user.state = demo_user.state or "SP"

    db.session.commit()


def _add_missing_columns(inspector, table_name, columns_to_add):
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    for column_name, ddl in columns_to_add.items():
        if column_name in existing_columns:
            continue
        db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
        db.session.commit()
        existing_columns.add(column_name)


def _normalize_legacy_values():
    statements = [
        (
            "UPDATE occurrence_mappings "
            "SET urgency_level = CASE "
            "WHEN lower(urgency_level) LIKE 'b%' THEN 'Baixa' "
            "WHEN lower(urgency_level) LIKE 'a%' THEN 'Alta' "
            "WHEN lower(urgency_level) LIKE 'c%' THEN 'Critica' "
            "ELSE 'Media' END "
            "WHERE urgency_level NOT IN ('Baixa', 'Media', 'Alta', 'Critica')"
        ),
        (
            "UPDATE occurrences "
            "SET urgency_level = CASE "
            "WHEN lower(urgency_level) LIKE 'b%' THEN 'Baixa' "
            "WHEN lower(urgency_level) LIKE 'a%' THEN 'Alta' "
            "WHEN lower(urgency_level) LIKE 'c%' THEN 'Critica' "
            "ELSE 'Media' END "
            "WHERE urgency_level NOT IN ('Baixa', 'Media', 'Alta', 'Critica')"
        ),
        (
            "UPDATE occurrences "
            "SET status = CASE "
            "WHEN lower(status) LIKE 'enc%' THEN 'Encaminhado' "
            "WHEN lower(status) LIKE 'em%' THEN 'Em triagem' "
            "WHEN lower(status) LIKE 'c%' THEN 'Concluido' "
            "ELSE 'Novo' END "
            "WHERE status NOT IN ('Novo', 'Em triagem', 'Encaminhado', 'Concluido')"
        ),
    ]
    for statement in statements:
        db.session.execute(text(statement))
    db.session.commit()


def migrate_schema():
    inspector = inspect(db.engine)

    _add_missing_columns(
        inspector,
        "products",
        {
            "brand": "VARCHAR(120) DEFAULT 'AloMana'",
            "subcategory_label": "VARCHAR(80) DEFAULT 'Produto'",
            "badge_label": "VARCHAR(80)",
            "shade_label": "VARCHAR(120)",
            "size_label": "VARCHAR(80)",
            "highlights_json": "TEXT DEFAULT '[]'",
            "rating": "FLOAT DEFAULT 4.8",
            "review_count": "INTEGER DEFAULT 0",
        },
    )
    _add_missing_columns(
        inspector,
        "users",
        {
            "full_name": "VARCHAR(160)",
            "phone": "VARCHAR(40)",
            "zip_code": "VARCHAR(16)",
            "street": "VARCHAR(160)",
            "number": "VARCHAR(20)",
            "complement": "VARCHAR(120)",
            "neighborhood": "VARCHAR(120)",
            "city": "VARCHAR(120)",
            "state": "VARCHAR(2)",
        },
    )
    _add_missing_columns(
        inspector,
        "occurrences",
        {
            "user_id": "INTEGER",
            "recipient_name": "VARCHAR(160)",
            "address_zip_code": "VARCHAR(16)",
            "address_street": "VARCHAR(160)",
            "address_number": "VARCHAR(20)",
            "address_complement": "VARCHAR(120)",
            "address_neighborhood": "VARCHAR(120)",
            "address_city": "VARCHAR(120)",
            "address_state": "VARCHAR(2)",
            "delivery_window": "VARCHAR(120)",
            "delivery_notes": "TEXT",
        },
    )

    _normalize_legacy_values()
