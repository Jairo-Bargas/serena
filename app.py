import os
import re
import secrets
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from datetime import timedelta

from flask import (Flask, abort, flash, jsonify, redirect, render_template, request,
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
IS_SQLITE = db_url.startswith("sqlite")
if IS_SQLITE:
    # En Render la base vive en el disco permanente (p. ej. sqlite:////var/data/serena.db)
    Path(db_url.split("sqlite:///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"] = {"timeout": 15}

db = SQLAlchemy(app)

if IS_SQLITE:
    from sqlalchemy import event

    with app.app_context():
        @event.listens_for(db.engine, "connect")
        def _sqlite_pragmas(conn, _record):
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")   # lecturas y escrituras a la vez sin bloquearse
            cur.execute("PRAGMA busy_timeout=15000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()


def utcnow():
    return datetime.now(timezone.utc)


def aware(dt):
    """SQLite devuelve fechas sin zona horaria: las tratamos como UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def add_months(dt, months):
    import calendar
    m = dt.month - 1 + months
    year, month = dt.year + m // 12, m % 12 + 1
    return dt.replace(year=year, month=month, day=min(dt.day, calendar.monthrange(year, month)[1]))


# ---------------------------------------------------------------- modelos

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    token = db.Column(db.String(32), unique=True, nullable=False, index=True)
    stamps = db.Column(db.Integer, nullable=False, default=0)
    cards_completed = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.String(500), nullable=False, default="")
    card_started_at = db.Column(db.DateTime(timezone=True))   # se fija al reiniciar la tarjeta
    expires_override = db.Column(db.DateTime(timezone=True))  # vencimiento extendido a mano
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

    @property
    def card_started(self):
        """Inicio de la tarjeta actual: el alta, un reinicio, o la visita que completó la anterior."""
        total = content.LOYALTY["total"]
        dates = [v.created_at for v in self.visits if v.stamp_number >= total]
        dates += [self.created_at] + ([self.card_started_at] if self.card_started_at else [])
        return max(aware(d) for d in dates)

    @property
    def card_expires(self):
        exp = add_months(self.card_started, content.LOYALTY["valid_months"])
        if self.expires_override:
            exp = max(exp, aware(self.expires_override))
        return exp

    @property
    def is_expired(self):
        return self.card_expires <= utcnow()

    @property
    def expires_soon(self):
        """Le queda un mes o menos (y todavía no venció)."""
        return not self.is_expired and self.card_expires - utcnow() <= timedelta(days=30)

    @property
    def expiry_text(self):
        """'te quedan 8 meses' / 'te quedan 12 días' / None si ya venció."""
        now = utcnow()
        exp = self.card_expires
        if exp <= now:
            return None
        months = (exp.year - now.year) * 12 + (exp.month - now.month)
        if add_months(now, months).date() > exp.date():
            months -= 1
        if months >= 1:
            return f"te queda{'n' if months > 1 else ''} {months} mes{'es' if months > 1 else ''}"
        days = max(1, (exp - now).days)
        return f"te queda{'n' if days > 1 else ''} {days} día{'s' if days > 1 else ''}"


class Visit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    service = db.Column(db.String(120), nullable=False)
    stamp_number = db.Column(db.Integer, nullable=False)
    discount = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class PushSub(db.Model):
    """Un celular de una clienta que aceptó recibir avisos."""
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False, index=True)
    endpoint = db.Column(db.String(600), unique=True, nullable=False)
    p256dh = db.Column(db.String(200), nullable=False)
    auth = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    client = db.relationship("Client", backref=db.backref("push_subs", cascade="all, delete-orphan"))


class Notice(db.Model):
    """Avisos automáticos ya enviados (para no repetirlos)."""
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    client = db.relationship("Client", backref=db.backref("notices", cascade="all, delete-orphan"))


class Setting(db.Model):
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()
    # columnas agregadas después de la primera versión (create_all no las suma a tablas existentes)
    from sqlalchemy import inspect, text
    _cols = {c["name"] for c in inspect(db.engine).get_columns("client")}
    for _name in ("card_started_at", "expires_override"):
        if _name not in _cols:
            with db.engine.begin() as _conn:
                _conn.execute(text(f"ALTER TABLE client ADD COLUMN {_name} TIMESTAMP"))


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
    notify_stamp(client, visit)
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


# ---------------------------------------------------------------- notificaciones push (web)

def setting(key, default=None):
    row = db.session.get(Setting, key)
    return row.value if row else default


def set_setting(key, value):
    row = db.session.get(Setting, key) or Setting(key=key, value="")
    row.value = value
    db.session.add(row)
    db.session.commit()


def vapid_keys():
    """Claves para firmar los avisos. Se generan solas la primera vez y quedan en la base."""
    pem, pub = setting("vapid_private"), setting("vapid_public")
    if not pem:
        import base64
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid
        v = Vapid()
        v.generate_keys()
        pem = v.private_pem().decode()
        raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        pub = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        set_setting("vapid_private", pem)
        set_setting("vapid_public", pub)
    return pem, pub


def _send(app_obj, sub_rows, payload):
    import json
    from py_vapid import Vapid
    from pywebpush import WebPushException, webpush
    with app_obj.app_context():
        pem, _ = vapid_keys()
        vapid = Vapid.from_pem(pem.encode())
        dead = []
        for sub_id, endpoint, p256dh, auth, card_url in sub_rows:
            data = dict(payload, url=payload["url"] or card_url)  # sin url fija: abre la tarjeta de esa clienta
            try:
                webpush({"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                        json.dumps(data), vapid_private_key=vapid,
                        vapid_claims={"sub": f"mailto:{content.BUSINESS['email']}"}, ttl=60 * 60 * 24)
            except WebPushException as e:
                if e.response is not None and e.response.status_code in (404, 410):
                    dead.append(sub_id)  # la clienta desinstaló o bloqueó los avisos
                else:
                    app_obj.logger.warning("push falló: %s", e)
            except Exception as e:  # nunca romper el flujo de Sheila por un aviso
                app_obj.logger.warning("push falló: %s", e)
        if dead:
            PushSub.query.filter(PushSub.id.in_(dead)).delete(synchronize_session=False)
            db.session.commit()


def send_push(client_ids, title, body, url=None):
    """Envía un aviso a los celulares de esas clientas, en segundo plano. Devuelve cuántos celulares.
    Si no se pasa url, al tocar el aviso cada clienta abre su propia tarjeta."""
    import threading
    q = PushSub.query
    if client_ids is not None:
        q = q.filter(PushSub.client_id.in_(list(client_ids)))
    rows = [(s.id, s.endpoint, s.p256dh, s.auth, f"/tarjeta/{s.client.token}") for s in q.all()]
    if rows:
        payload = {"title": title, "body": body, "url": url}
        threading.Thread(target=_send, args=(app, rows, payload), daemon=True).start()
    return len(rows)


def notify_stamp(client, visit):
    if not client.push_subs:
        return
    total = content.LOYALTY["total"]
    url = f"/tarjeta/{client.token}"
    if visit.stamp_number >= total:
        title, body = "¡Completaste tu tarjeta! 🎉", f"Hoy tuviste {visit.discount}% OFF. Ya empezás una tarjeta nueva."
    elif visit.discount:
        title, body = f"¡Sello {visit.stamp_number}! 🎉", f"Este servicio tiene {visit.discount}% OFF."
    else:
        title = "¡Sumaste un sello! 💅"
        body = f"Llevás {visit.stamp_number} de {total}."
        nxt = client.next_reward
        if nxt:
            left = nxt[0] - client.stamps
            body += f" ¡Tu próximo servicio tiene {nxt[1]}% OFF!" if left == 1 else f" Te faltan {left} para tu {nxt[1]}% OFF."
    send_push([client.id], title, body, url)


def run_daily_notices(force=False):
    """Avisos de vencimiento (7 días y 1 día antes). Corre como mucho cada 6 horas,
    cuando Sheila usa el panel o el escáner. No hace falta ningún cron."""
    last = setting("notices_last_run")
    now = utcnow()
    if not force and last and now - datetime.fromisoformat(last) < timedelta(hours=6):
        return 0
    set_setting("notices_last_run", now.isoformat())
    sent = 0
    for c in Client.query.join(PushSub).distinct().all():
        if c.is_expired:
            continue
        days = (c.card_expires - now).days
        for limit, text in ((1, "¡Tu tarjeta vence mañana!"), (7, "Tu tarjeta vence en una semana")):
            if days < limit:
                kind = f"vence{limit}:{c.card_expires.date().isoformat()}"
                if not Notice.query.filter_by(client_id=c.id, kind=kind).first():
                    db.session.add(Notice(client_id=c.id, kind=kind))
                    db.session.commit()
                    msg = f"Tenés {c.stamps} sellos. Reservá tu turno para no perderlos 💅"
                    sent += send_push([c.id], text, msg, f"/tarjeta/{c.token}")
                break
    return sent


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
        sent = request.form.get("csrf") or request.headers.get("X-CSRF")
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
        vapid_public=vapid_keys()[1],
        services=content.LOYALTY_SERVICE_CHOICES,
        card_url=url_for("tarjeta", token=token, _external=True),
    )


@app.route("/tarjeta/<token>/estado")
def tarjeta_estado(token):
    """Lo consulta la tarjeta de la clienta cada pocos segundos para enterarse de sellos nuevos."""
    client = Client.query.filter_by(token=token).first_or_404()
    last = client.visits[0] if client.visits else None
    resp = jsonify(stamps=client.stamps, cards=client.cards_completed, last_visit=last.id if last else None,
                   last_stamp=last.stamp_number if last else None, last_discount=last.discount if last else 0)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/sw.js")
def service_worker():
    js = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Serena Nails', {
    body: d.body || '', icon: '/static/icons/icon-192.png', badge: '/static/icons/badge-96.png',
    data: { url: d.url || '/' },
  }));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = new URL(e.notification.data.url, self.location.origin).href;
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then((ws) => {
    for (const w of ws) { if (w.url === url && 'focus' in w) return w.focus(); }
    return clients.openWindow(url);
  }));
});
"""
    resp = app.response_class(js, mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/tarjeta/<token>/avisos", methods=["POST"])
def tarjeta_avisos(token):
    client = Client.query.filter_by(token=token).first_or_404()
    data = request.get_json(silent=True) or {}
    endpoint = (data.get("endpoint") or "")[:600]
    keys = data.get("keys") or {}
    if not endpoint.startswith("https://") or not keys.get("p256dh") or not keys.get("auth"):
        return jsonify(error="Suscripción inválida"), 400
    sub = PushSub.query.filter_by(endpoint=endpoint).first() or PushSub(endpoint=endpoint)
    sub.client_id, sub.p256dh, sub.auth = client.id, keys["p256dh"][:200], keys["auth"][:100]
    db.session.add(sub)
    db.session.commit()
    return jsonify(ok=True)


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
    everyone = Client.query.order_by(Client.name).all()
    expired = [c for c in everyone if c.is_expired]
    expiring = [c for c in everyone if c.expires_soon]
    if request.args.get("filtro") == "vencidas":
        clients = expired
    elif request.args.get("filtro") == "por-vencer":
        clients = expiring
    stats["expired"], stats["expiring"] = len(expired), len(expiring)
    stats["push"] = db.session.query(PushSub.client_id).distinct().count()
    run_daily_notices()
    return render_template("admin/index.html", clients=clients, q=q, stats=stats, filtro=request.args.get("filtro"))


@app.route("/admin/avisos", methods=["POST"])
@admin_required
def admin_broadcast():
    title = request.form.get("title", "").strip()[:60] or "Serena Nails"
    body = request.form.get("body", "").strip()[:180]
    if not body:
        flash("Escribí el mensaje del aviso.", "error")
        return redirect(url_for("admin"))
    n = send_push(None, title, body)
    flash(f"Aviso enviado a {n} celular{'es' if n != 1 else ''}." if n else "Todavía ninguna clienta activó los avisos.", "ok" if n else "info")
    return redirect(url_for("admin"))


@app.route("/admin/exportar/<tipo>")
@admin_required
def admin_export(tipo):
    """Descarga un CSV que abre directo en Excel (separador ; y tildes OK)."""
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    total = content.LOYALTY["total"]
    if tipo == "clientas":
        w.writerow(["Nombre", "Celular", "Sellos actuales", f"Tarjetas completas ({total} sellos)",
                     "Visitas totales", "Primera visita", "Última visita", "Cliente desde", "Vence la tarjeta",
                     "Estado", "Notas"])
        for c in Client.query.order_by(Client.name).all():
            fechas = sorted(v.created_at for v in c.visits)
            w.writerow([c.name, f"0{c.phone}", c.stamps, c.cards_completed, len(c.visits),
                        format_fecha(fechas[0]) if fechas else "", format_fecha(fechas[-1]) if fechas else "",
                        format_fecha(c.created_at), format_fecha(c.card_expires),
                        "Vencida" if c.is_expired else ("Vence pronto" if c.expires_soon else "Vigente"), c.notes])
    elif tipo == "visitas":
        w.writerow(["Fecha", "Hora", "Clienta", "Celular", "Servicio", "N° de sello", "Descuento"])
        for v in Visit.query.order_by(Visit.created_at.desc()).all():
            local = v.created_at - timedelta(hours=3)  # hora de Uruguay
            w.writerow([local.strftime("%d/%m/%Y"), local.strftime("%H:%M"), v.client.name, f"0{v.client.phone}",
                        v.service, v.stamp_number, f"{v.discount}%" if v.discount else ""])
    else:
        abort(404)
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return app.response_class(
        "﻿" + buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="serena-{tipo}-{fecha}.csv"'})


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
    flash(f"Tarjeta creada para {client.first_name} con {client.stamps} sellos de bienvenida.", "ok")
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


@app.route("/admin/clientas/<int:client_id>/reiniciar", methods=["POST"])
@admin_required
def admin_reset_card(client_id):
    client = db.get_or_404(Client, client_id)
    client.stamps = 0
    client.card_started_at = utcnow()
    client.expires_override = None
    db.session.commit()
    flash(f"Tarjeta de {client.first_name} reiniciada: 0 sellos y {content.LOYALTY['valid_months']} meses de vigencia.", "ok")
    return redirect(url_for("tarjeta", token=client.token))


@app.route("/admin/clientas/<int:client_id>/extender", methods=["POST"])
@admin_required
def admin_extend_card(client_id):
    client = db.get_or_404(Client, client_id)
    base = max(client.card_expires, utcnow())  # si ya venció, el mes cuenta desde hoy
    client.expires_override = add_months(base, 1)
    db.session.commit()
    flash(f"Tarjeta extendida hasta el {format_fecha(client.card_expires)}.", "ok")
    return redirect(url_for("tarjeta", token=client.token))


@app.route("/admin/clientas/<int:client_id>/eliminar", methods=["POST"])
@admin_required
def admin_delete_client(client_id):
    client = db.get_or_404(Client, client_id)
    db.session.delete(client)
    db.session.commit()
    flash("Clienta eliminada.", "info")
    return redirect(url_for("admin"))


# ---------------------------------------------------------------- escáner (API JSON)

DUPLICATE_WINDOW = timedelta(hours=3)


def client_json(client, visit=None):
    nxt = client.next_reward
    return {
        "id": client.id, "name": client.name, "first_name": client.first_name, "token": client.token,
        "stamps": client.stamps, "total": content.LOYALTY["total"], "cards": client.cards_completed,
        "next_reward": {"stamp": nxt[0], "pct": nxt[1]} if nxt else None,
        "visit": {"id": visit.id, "stamp": visit.stamp_number, "discount": visit.discount,
                  "service": visit.service} if visit else None,
        "card_url": url_for("tarjeta", token=client.token),
        "expired": client.is_expired,
        "expires": format_fecha(client.card_expires),
    }


@app.route("/admin/escanear")
@admin_required
def admin_scan():
    run_daily_notices()
    return render_template("admin/scan.html", services=content.LOYALTY_SERVICE_CHOICES)


@app.route("/admin/api/sello", methods=["POST"])
@admin_required
def api_add_stamp():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    client = Client.query.filter_by(token=token).first()
    if not client:
        return jsonify(error="No encontré esa tarjeta. ¿Es un QR de una tarjeta de Serena?"), 404
    last = client.visits[0] if client.visits else None
    if last and not data.get("force"):
        created = last.created_at if last.created_at.tzinfo else last.created_at.replace(tzinfo=timezone.utc)
        ago = utcnow() - created
        if ago < DUPLICATE_WINDOW:
            return jsonify(confirm=True, minutes=int(ago.total_seconds() // 60), client=client_json(client)), 409
    visit = register_visit(client, (data.get("service") or "Servicio")[:120])
    return jsonify(ok=True, client=client_json(client, visit))


@app.route("/admin/api/visita/<int:visit_id>", methods=["POST"])
@admin_required
def api_update_visit(visit_id):
    visit = db.get_or_404(Visit, visit_id)
    data = request.get_json(silent=True) or {}
    if data.get("undo"):
        client = visit.client
        if client.visits and client.visits[0].id == visit.id:
            undo_last_visit(client)
            return jsonify(ok=True, client=client_json(client))
        return jsonify(error="Solo se puede deshacer el último sello."), 400
    visit.service = (data.get("service") or visit.service)[:120]
    db.session.commit()
    return jsonify(ok=True)


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=bool(os.environ.get("FLASK_DEBUG")))
