import os
import re
import secrets
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)
from flask_sqlalchemy import SQLAlchemy

import content

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "dev-solo-local-cambiar"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("RENDER"))
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 30
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 60 * 60 * 24 * 7

db_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'serena.db'}")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- modelos

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, index=True)
    stamps = db.Column(db.Integer, nullable=False, default=0)
    cards_completed = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    visits = db.relationship("Visit", backref="client", cascade="all, delete-orphan",
                             order_by="Visit.id.desc()")

    @property
    def first_name(self):
        return self.name.split()[0] if self.name else ""

    @property
    def next_stamp(self):
        return self.stamps + 1

    @property
    def next_reward(self):
        """(n° de sello, % descuento) del próximo premio."""
        for n, pct in sorted(content.LOYALTY["rewards"].items()):
            if n > self.stamps:
                return n, pct
        return None


class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    service = db.Column(db.String(120), nullable=False)
    stamp_number = db.Column(db.Integer, nullable=False)
    discount = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------- lógica de fidelización

def normalize_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("598"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits


def register_visit(client, service):
    """Suma un sello. Devuelve la visita creada (con el descuento que corresponde)."""
    total = content.LOYALTY["total"]
    n = client.stamps + 1
    discount = content.LOYALTY["rewards"].get(n, 0)
    visit = Visit(client=client, service=service, stamp_number=n, discount=discount)
    if n >= total:
        client.stamps = 0
        client.cards_completed += 1
    else:
        client.stamps = n
    db.session.add(visit)
    db.session.commit()
    return visit


def undo_last_visit(client):
    last = client.visits[0] if client.visits else None
    if not last:
        return False
    if client.stamps == 0 and client.cards_completed > 0 and last.stamp_number >= content.LOYALTY["total"]:
        client.cards_completed -= 1
    client.stamps = last.stamp_number - 1
    db.session.delete(last)
    db.session.commit()
    return True


# ---------------------------------------------------------------- helpers

def static_exists(rel):
    return (BASE_DIR / "static" / rel).is_file()


def media():
    hero = content.HERO_VIDEO or ("video/hero.mp4" if static_exists("video/hero.mp4") else None)
    space = content.SPACE_VIDEOS or sorted(
        f"video/{p.name}" for p in (BASE_DIR / "static" / "video").glob("espacio*.mp4"))
    return hero, space


def is_admin():
    return session.get("admin") is True


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_admin():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400)


def asset(filename):
    """URL de un archivo estático con versión (mtime) para invalidar caché en cada deploy."""
    path = BASE_DIR / "static" / filename
    v = int(path.stat().st_mtime) if path.is_file() else 0
    return url_for("static", filename=filename, v=v)


@app.context_processor
def inject_globals():
    return {
        "asset": asset,
        "B": content.BUSINESS,
        "LOYALTY": content.LOYALTY,
        "csrf_token": csrf_token,
        "is_admin": is_admin(),
        "year": datetime.now().year,
    }


@app.template_filter("uyu")
def format_uyu(value):
    return f"${value:,}".replace(",", ".") if value is not None else "Consultar"


@app.template_filter("fecha")
def format_fecha(dt):
    meses = "ene feb mar abr may jun jul ago sep oct nov dic".split()
    return f"{dt.day} {meses[dt.month - 1]} {dt.year}"


# ---------------------------------------------------------------- sitio público

@app.route("/")
def home():
    hero_video, space_videos = media()
    return render_template(
        "index.html",
        services=content.SERVICES,
        gallery=content.GALLERY,
        hero_video=hero_video,
        space_videos=space_videos,
    )


@app.route("/fidelidad")
def fidelidad():
    return render_template("fidelidad.html")


@app.route("/tarjeta/<token>")
def tarjeta(token):
    client = Client.query.filter_by(token=token).first_or_404()
    return render_template(
        "tarjeta.html",
        client=client,
        services=content.LOYALTY_SERVICE_CHOICES,
        card_url=url_for("tarjeta", token=token, _external=True),
    )


@app.route("/manifest.webmanifest")
def manifest():
    resp = app.response_class(render_template("manifest.json"), mimetype="application/manifest+json")
    return resp


@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory("static", "sitemap.xml")


@app.route("/robots.txt")
def robots():
    return app.response_class(
        f"User-agent: *\nDisallow: /admin\nDisallow: /tarjeta/\nSitemap: {content.BUSINESS['url']}/sitemap.xml\n",
        mimetype="text/plain")


# ---------------------------------------------------------------- admin

@app.route("/admin/ingresar", methods=["GET", "POST"])
def admin_login():
    password = os.environ.get("ADMIN_PASSWORD")
    if request.method == "POST":
        if password and secrets.compare_digest(request.form.get("password", ""), password):
            session.clear()
            session.permanent = True
            session["admin"] = True
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("admin"))
        time.sleep(1.2)
        flash("Contraseña incorrecta", "error")
    return render_template("admin/login.html", configured=bool(password))


@app.route("/admin/salir", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        digits = normalize_phone(q)
        cond = Client.name.ilike(f"%{q}%")
        if digits:
            cond = cond | Client.phone.contains(digits)
        query = query.filter(cond)
    clients = query.order_by(Client.name).all()
    stats = {
        "clients": Client.query.count(),
        "visits_month": Visit.query.filter(
            Visit.created_at >= datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ).count(),
        "rewards_soon": Client.query.filter(Client.stamps.in_([n - 1 for n in content.LOYALTY["rewards"]])).count(),
    }
    return render_template("admin/index.html", clients=clients, q=q, stats=stats)


@app.route("/admin/clientas", methods=["POST"])
@admin_required
def admin_create_client():
    name = request.form.get("name", "").strip()
    phone = normalize_phone(request.form.get("phone"))
    if not name or len(phone) < 8:
        flash("Completá nombre y un celular válido.", "error")
        return redirect(url_for("admin"))
    existing = Client.query.filter_by(phone=phone).first()
    if existing:
        flash(f"{existing.name} ya tiene tarjeta.", "info")
        return redirect(url_for("tarjeta", token=existing.token))
    client = Client(name=name, phone=phone, token=secrets.token_urlsafe(9),
                    stamps=content.LOYALTY["welcome"])
    db.session.add(client)
    db.session.commit()
    flash(f"Tarjeta creada para {client.first_name} con {client.stamps} sellos de regalo.", "ok")
    return redirect(url_for("tarjeta", token=client.token))


@app.route("/admin/clientas/<int:client_id>/sello", methods=["POST"])
@admin_required
def admin_add_stamp(client_id):
    client = db.get_or_404(Client, client_id)
    service = request.form.get("service", "").strip() or "Servicio"
    visit = register_visit(client, service[:120])
    if visit.discount:
        flash(f"Sello {visit.stamp_number} sumado. Este servicio lleva {visit.discount}% de descuento.", "reward")
    else:
        flash(f"Sello {visit.stamp_number} sumado.", "ok")
    return redirect(url_for("tarjeta", token=client.token))


@app.route("/admin/clientas/<int:client_id>/deshacer", methods=["POST"])
@admin_required
def admin_undo_stamp(client_id):
    client = db.get_or_404(Client, client_id)
    flash("Último sello eliminado." if undo_last_visit(client) else "No hay sellos para deshacer.", "info")
    return redirect(url_for("tarjeta", token=client.token))


@app.route("/admin/clientas/<int:client_id>/editar", methods=["POST"])
@admin_required
def admin_edit_client(client_id):
    client = db.get_or_404(Client, client_id)
    client.name = request.form.get("name", client.name).strip() or client.name
    client.notes = request.form.get("notes", "").strip()[:500]
    db.session.commit()
    flash("Datos guardados.", "ok")
    return redirect(url_for("tarjeta", token=client.token))


@app.route("/admin/clientas/<int:client_id>/eliminar", methods=["POST"])
@admin_required
def admin_delete_client(client_id):
    client = db.get_or_404(Client, client_id)
    db.session.delete(client)
    db.session.commit()
    flash("Clienta eliminada.", "info")
    return redirect(url_for("admin"))


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=bool(os.environ.get("FLASK_DEBUG")))
