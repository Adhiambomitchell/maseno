"""Maseno First-Year Guide: Flask + SQLite web app for new Maseno University students."""
import hmac
import json
import logging
import mimetypes
import os
import secrets
import socket
import sqlite3
import urllib.request
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from markupsafe import escape
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "maseno.db")
UPLOADS = os.path.join(BASE, "uploads")
PAPERS = os.path.join(BASE, "papers")
DOC_EXT = {"pdf", "png", "jpg", "jpeg"}
PAPER_EXT = {"pdf", "doc", "docx", "ppt", "pptx"}

USE_PG = config.DATABASE_URL.startswith(("postgres://", "postgresql://"))
STORE_IN_DB = config.STORE_FILES_IN_DB
if USE_PG:
    import psycopg2
    import psycopg2.extras
    DB_INTEGRITY = (sqlite3.IntegrityError, psycopg2.IntegrityError)
else:
    DB_INTEGRITY = (sqlite3.IntegrityError,)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = config.PRODUCTION
app.config["PERMANENT_SESSION_LIFETIME"] = 60 * 60 * 24 * 14
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Flask-Mail & Tokenizer Configuration
# ---------------------------------------------------------------------------
app.config["MAIL_SERVER"] = getattr(config, "MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = getattr(config, "MAIL_PORT", 587)
app.config["MAIL_USE_TLS"] = getattr(config, "MAIL_USE_TLS", True)
app.config["MAIL_USE_SSL"] = getattr(config, "MAIL_USE_SSL", False)
app.config["MAIL_USERNAME"] = getattr(config, "MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = getattr(config, "MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = getattr(config, "MAIL_DEFAULT_SENDER", config.MAIL_USERNAME)

mail = Mail(app)
MAIL_CONFIGURED = bool(config.BREVO_API_KEY and config.MAIL_DEFAULT_SENDER) or bool(config.MAIL_USERNAME and config.MAIL_PASSWORD)
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

# ---------------------------------------------------------------------------
# Content that lives in code (edit freely)
# ---------------------------------------------------------------------------
REQUIRED_DOCS = [
    {"key": "admission_letter", "title": "Admission letter", "icon": "💌",
     "desc": "The official letter offering you a place at Maseno University.", "place": "admin",
     "office": "Registrar (Academic and Student Affairs), Administration Block"},
    {"key": "national_id", "title": "National ID or passport", "icon": "🪪",
     "desc": "A clear scan of the page with your photo and number.", "place": "admin",
     "office": "Registrar (Academic and Student Affairs), Administration Block"},
    {"key": "results_slip", "title": "KCSE result slip or certificate", "icon": "🎓",
     "desc": "Your secondary school results (or equivalent).", "place": "admin",
     "office": "Registrar (Academic and Student Affairs), Administration Block"},
    {"key": "fee_receipt", "title": "Fee payment receipt", "icon": "🧾",
     "desc": "Bank slip or payment confirmation for your fees.", "place": "finance",
     "office": "Finance Office"},
    {"key": "medical_form", "title": "Medical form", "icon": "🩺",
     "desc": "The filled-in medical form and parent or guardian consent.", "place": "health",
     "office": "University Health Centre"},
    {"key": "passport_photo", "title": "Passport photo", "icon": "📸",
     "desc": "Recent photo on a plain background, used for your student ID.", "place": "admin",
     "office": "Student ID desk, Administration Block"},
]

SEED_LOCATIONS = [
    ("gate", "Main Gate", "admin", "Maseno University main gate", -0.0066, 34.5990, "Where you enter campus from the Kisumu-Busia road."),
    ("admin", "Administration Block", "admin", "Maseno University Administration Block", -0.0050, 34.6003, "Registrar, admissions and student ID desk."),
    ("finance", "Finance Office", "admin", "Maseno University Finance Office", -0.0051, 34.6006, "Fee payments, receipts and balances."),
    ("library", "Main Library", "library", "Maseno University Library", -0.0044, 34.6012, "Study space, books and Wi-Fi."),
    ("health", "University Health Centre", "health", "Maseno University Health Centre", -0.0038, 34.6022, "Medical checks and first aid."),
    ("computing", "School of Computing and Informatics", "lecture", "Maseno University School of Computing and Informatics", -0.0040, 34.6000, "Computing lectures and lab practicals."),
    ("maths", "School of Mathematics, Statistics and Actuarial Science", "lecture", "Maseno University School of Mathematics Statistics and Actuarial Science", -0.0046, 34.5996, "Mathematics and statistics lectures."),
    ("lectures", "Main Lecture Theatres", "lecture", "Maseno University lecture theatres", -0.0049, 34.6016, "Large first-year lectures."),
    ("cafeteria", "Cafeteria", "food", "Maseno University cafeteria", -0.0047, 34.6008, "Meals and snacks."),
    ("hostels", "Student Hostels", "hostel", "Maseno University hostels", -0.0058, 34.6024, "On-campus accommodation, with priority for first years."),
    ("sports", "Sports Grounds", "sports", "Maseno University sports ground", -0.0036, 34.6034, "Football, athletics and the freshers' sports day."),
    ("stage", "Maseno Town Matatu Stage", "transport", "Maseno town matatu stage", -0.0075, 34.5985, "Matatus to and from Kisumu."),
]

CHECKLIST = [
    ("fees", "Pay semester and accommodation fees, and keep every receipt"),
    ("print", "Print your admission letter and fee receipt"),
    ("originals", "Pack original certificates plus photocopies"),
    ("photos", "Carry passport photos for your student ID"),
    ("docs", "Upload all documents in this app"),
    ("bedding", "Pack bedding, a padlock and basic toiletries"),
    ("power", "Pack phone and laptop chargers and a power extension"),
    ("whatsapp", "Join your course and hostel WhatsApp groups"),
    ("map", "Walk to your lecture halls once before classes start"),
    ("event", "Register for at least one freshers' event"),
]

TIPS = [
    ("🚌", "Getting here", "The main campus is in Maseno Township on the Kisumu-Busia road, about 25 km from Kisumu City. Matatus run from Kisumu to Maseno."),
    ("🛏️", "Accommodation", "First years get priority for on-campus rooms. Rooms are allocated first come, first served, so pay your fees early."),
    ("🍽️", "Food", "The university runs cafeterias on a pay-as-you-eat basis, and meals are subsidised."),
    ("🩺", "Health", "Main campus students are covered by a university medical scheme through the Health Centre."),
    ("🌍", "Fun fact", "Maseno University sits right on the Equator, so you study at latitude 0°."),
    ("📣", "Always check official notices", "Fees, dates and deadlines change. Confirm them on maseno.ac.ke or with the Registrar's office."),
]

GROUP_CATEGORIES = ["General freshers", "Course and department", "Hostels and accommodation",
                    "Clubs and societies", "Study groups"]
EVENT_CATEGORIES = ["Orientation", "Academic", "Social", "Sports", "Career", "Wellbeing"]


def sample_events():
    base = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    def d(days, hour):
        return (base + timedelta(days=days)).replace(hour=hour).strftime("%Y-%m-%d %H:%M")
    return [
        ("Freshers' Welcome and Orientation", "Meet the Vice-Chancellor's team, learn how the university works and collect your orientation pack.", "Orientation", d(3, 9), "Main Lecture Theatres", 0),
        ("Campus Walking Tour", "A guided walk past the offices, library, lecture halls and cafeteria so you never get lost.", "Orientation", d(4, 10), "Main Gate", 60),
        ("Library and eLearning Workshop", "Learn to find books, past papers and how to use the eLearning platform.", "Academic", d(5, 14), "Main Library", 80),
        ("Clubs and Societies Fair", "Talk to student clubs and sign up for the ones that fit you.", "Social", d(8, 10), "Cafeteria area", 0),
        ("Freshers' Sports Day", "Football, volleyball and relays. Come and make friends.", "Sports", d(10, 15), "Sports Grounds", 0),
        ("Budgeting and Wellbeing Talk", "Manage money, sleep and stress in your first semester.", "Wellbeing", d(12, 16), "Main Lecture Theatres", 150),
    ]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
class PGConn:
    """Small wrapper so the rest of the app can use the same calls for SQLite and Postgres."""

    def __init__(self, url):
        self.conn = psycopg2.connect(url, connect_timeout=15)

    def execute(self, sql, params=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql.replace("?", "%s"), tuple(params) if params else None)
        return cur

    def executemany(self, sql, seq):
        for p in seq:
            self.execute(sql, p).close()

    def executescript(self, script):
        for stmt in script.split(";"):
            if stmt.strip():
                self.execute(stmt).close()

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()


def connect_db():
    if USE_PG:
        return PGConn(config.DATABASE_URL)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ddl(script):
    if USE_PG:
        script = (script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                        .replace(" REAL", " DOUBLE PRECISION").replace(" BLOB", " BYTEA"))
    return script


def get_db():
    if "db" not in g:
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def init_db():
    os.makedirs(UPLOADS, exist_ok=True)
    os.makedirs(PAPERS, exist_ok=True)
    db = connect_db()
    db.executescript(_ddl("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL, 
        password TEXT NOT NULL, 
        reg_no TEXT, 
        course TEXT,
        role TEXT DEFAULT 'student', 
        is_verified INTEGER DEFAULT 0,
        created TEXT
    );
    CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        doc_key TEXT NOT NULL, filename TEXT NOT NULL, original TEXT, status TEXT DEFAULT 'pending',
        note TEXT, uploaded_at TEXT, UNIQUE(user_id, doc_key));
    CREATE TABLE IF NOT EXISTS locations(id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE, name TEXT,
        category TEXT, query TEXT, lat REAL, lng REAL, description TEXT, verified INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS papers(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, course TEXT,
        unit_code TEXT, year TEXT, filename TEXT, original TEXT, uploaded_at TEXT);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT,
        category TEXT, starts TEXT, venue TEXT, capacity INTEGER DEFAULT 0, created TEXT);
    CREATE TABLE IF NOT EXISTS registrations(id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER,
        user_id INTEGER, created TEXT, UNIQUE(event_id, user_id));
    CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT,
        link TEXT, description TEXT, added_by INTEGER, status TEXT DEFAULT 'pending', created TEXT);
    CREATE TABLE IF NOT EXISTS announcements(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS blobs(id INTEGER PRIMARY KEY AUTOINCREMENT, data BLOB, mimetype TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS checklist(user_id INTEGER, item TEXT, PRIMARY KEY(user_id, item));
    """))
    cols = [] if USE_PG else [r[1] for r in db.execute("PRAGMA table_info(users)")]
    if not USE_PG and "is_verified" not in cols:  # database from an older version
        db.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
        db.execute("UPDATE users SET is_verified=1")
    if not db.execute("SELECT 1 FROM locations").fetchone():
        db.executemany("INSERT INTO locations(slug,name,category,query,lat,lng,description) VALUES(?,?,?,?,?,?,?)", SEED_LOCATIONS)
    if not db.execute("SELECT 1 FROM events").fetchone():
        db.executemany("INSERT INTO events(title,description,category,starts,venue,capacity,created) VALUES(?,?,?,?,?,?,?)",
                       [e + (now(),) for e in sample_events()])
    if not db.execute("SELECT 1 FROM announcements").fetchone():
        db.execute("INSERT INTO announcements(title,body,created) VALUES(?,?,?)",
                   ("Karibu Maseno!", "Upload your documents here, then take the originals to the offices shown. Check Events for orientation week.", now()))
    if not db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        admin_pw = config.ADMIN_PASSWORD
        if not admin_pw:
            admin_pw = secrets.token_urlsafe(12)
            logging.getLogger(__name__).warning("FIRST RUN: admin login is %s / %s (set ADMIN_PASSWORD in .env to choose your own)",
                                                config.ADMIN_EMAIL, admin_pw)
        db.execute("INSERT INTO users(name,email,password,role,is_verified,created) VALUES(?,?,?,?,1,?)",
                   ("Admin", config.ADMIN_EMAIL, generate_password_hash(admin_pw), "admin", now()))
    db.commit()
    db.close()


def allowed(filename, exts):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts


def store_file(file, folder, stored_name):
    """Save an upload. Returns the value to keep in the 'filename' column ('db:<id>' or a file name)."""
    if STORE_IN_DB:
        data = file.read()
        mime = mimetypes.guess_type(stored_name)[0] or "application/octet-stream"
        db = get_db()
        if USE_PG:
            bid = db.execute("INSERT INTO blobs(data,mimetype,created) VALUES(?,?,?) RETURNING id",
                             (psycopg2.Binary(data), mime, now())).fetchone()[0]
        else:
            bid = db.execute("INSERT INTO blobs(data,mimetype,created) VALUES(?,?,?)", (data, mime, now())).lastrowid
        db.commit()
        return f"db:{bid}"
    file.save(os.path.join(folder, stored_name))
    return stored_name


def delete_file(folder, filename):
    if not filename:
        return
    if filename.startswith("db:"):
        db = get_db()
        db.execute("DELETE FROM blobs WHERE id=?", (int(filename[3:]),))
        db.commit()
    else:
        try:
            os.remove(os.path.join(folder, filename))
        except OSError:
            pass


def serve_file(folder, filename, as_attachment=False, download_name=None):
    if filename.startswith("db:"):
        row = get_db().execute("SELECT data, mimetype FROM blobs WHERE id=?", (int(filename[3:]),)).fetchone()
        if not row:
            abort(404)
        resp = Response(bytes(row["data"]), mimetype=row["mimetype"])
        if as_attachment:
            resp.headers["Content-Disposition"] = 'attachment; filename="%s"' % secure_filename(download_name or "file")
        return resp
    return send_from_directory(folder, filename, as_attachment=as_attachment, download_name=download_name)


@app.template_filter("dt")
def dt_filter(s, fmt="%a %d %b, %I:%M %p"):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M").strftime(fmt).replace(" 0", " ")
    except (TypeError, ValueError):
        return s


@app.context_processor
def inject_globals():
    key = getattr(config, "GEOAPIFY_API_KEY", "")
    return {
        "maps_key": key, 
        "campus_center": config.CAMPUS_CENTER,
        "max_mb": config.MAX_UPLOAD_MB
    }


# ---------------------------------------------------------------------------
# Auth & Email Verification Helpers
# ---------------------------------------------------------------------------
def deliver_email(to, subject, html):
    """Send through Brevo's HTTPS API if configured (works where SMTP ports are blocked), else SMTP."""
    if config.BREVO_API_KEY:
        payload = json.dumps({"sender": {"name": "Maseno First-Year Guide", "email": config.MAIL_DEFAULT_SENDER},
                              "to": [{"email": to}], "subject": subject, "htmlContent": html}).encode()
        req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=payload, method="POST",
                                     headers={"api-key": config.BREVO_API_KEY, "content-type": "application/json",
                                              "accept": "application/json"})
        urllib.request.urlopen(req, timeout=15).read()
        return
    msg = Message(subject=subject, recipients=[to], html=html)
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(15)  # never let a slow mail server freeze the page
    try:
        mail.send(msg)
    finally:
        socket.setdefaulttimeout(old_timeout)


def send_verification_email(user_email, user_name):
    """Send the link. Returns True if it was sent. Never raises, never hangs for long."""
    if not MAIL_CONFIGURED:
        return False
    token = serializer.dumps(user_email, salt='email-confirm')
    confirm_url = url_for('confirm_email', token=token, _external=True)

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #0B5FA5;">Welcome to Maseno First-Year Guide, {escape(user_name)}!</h2>
        <p>Thank you for registering. Please confirm your email address to complete your account setup.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{confirm_url}" style="background-color: #0B5FA5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">Verify Email Address</a>
        </div>
        <p style="color: #666; font-size: 13px;">Or copy and paste this link into your browser:<br><a href="{confirm_url}">{confirm_url}</a></p>
        <hr style="border: none; border-top: 1px solid #eee; margin-top: 30px;">
        <p style="color: #999; font-size: 12px;">This link will expire in 24 hours.</p>
    </div>
    """

    try:
        deliver_email(user_email, "Verify Your Email - Maseno First-Year Guide", html_body)
        return True
    except Exception:
        app.logger.exception("Could not send verification email to %s", user_email)
        return False



@app.before_request
def load_user():
    g.user = None
    if session.get("uid"):
        g.user = get_db().execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            flash("Log in first to continue.", "warn")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None or g.user["role"] != "admin":
            abort(403)
        return view(*a, **kw)
    return wrapped


# ---------------------------------------------------------------------------
# Security: CSRF protection, headers, friendly error pages
# ---------------------------------------------------------------------------
@app.before_request
def csrf_protect():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST":
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
        if not hmac.compare_digest(sent, session["csrf"]):
            abort(400)


@app.context_processor
def inject_csrf():
    return {"csrf_token": lambda: session.get("csrf", "")}


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return resp


ERRORS = {
    400: ("Please try again", "Your session expired or the form was out of date. Go back, refresh the page and try again."),
    403: ("Not allowed", "You don't have permission to open this page."),
    404: ("Page not found", "We couldn't find that page."),
    413: ("File too large", f"Files can be at most {config.MAX_UPLOAD_MB} MB. Choose a smaller file and try again."),
    500: ("Something went wrong", "That was our mistake. Please try again in a moment."),
}


def _error_page(e):
    code = getattr(e, "code", 500)
    title, text = ERRORS.get(code, ERRORS[500])
    return render_template("error.html", code=code, title=title, text=text), code


for _code in ERRORS:
    app.register_error_handler(_code, _error_page)


@app.route("/healthz")
def healthz():
    """Cheap check for uptime monitors. Does not touch the database."""
    return "ok", 200, {"Cache-Control": "no-store"}


@app.route("/")
def index():
    if g.user:
        return redirect(url_for("admin_tab", tab="overview") if g.user["role"] == "admin" else url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        name, email, pw = f.get("name", "").strip(), f.get("email", "").strip().lower(), f.get("password", "")
        if not name or "@" not in email or len(pw) < 6:
            flash("Fill in your name and email, and use a password of at least 6 characters.", "error")
            return render_template("register.html", form=f)
        db = get_db()
        try:
            db.execute("INSERT INTO users(name,email,password,reg_no,course,role,is_verified,created) VALUES(?,?,?,?,?,'student',0,?)",
                       (name, email, generate_password_hash(pw), f.get("reg_no", "").strip(), f.get("course", "").strip(), now()))
            db.commit()
            
            if MAIL_CONFIGURED:
                send_verification_email(email, name)
            else:  # no email set up, so don't lock students out
                db.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
                db.commit()
            
        except DB_INTEGRITY:

            
            db.rollback()
            flash("That email is already registered. Try logging in.", "error")
            return render_template("register.html", form=f)
            
        flash("Registration successful! Check your email (and spam) for the verification link." if MAIL_CONFIGURED
              else "Registration successful! You can log in now.", "ok")
        return redirect(url_for("login"))
    return render_template("register.html", form={})


@app.route("/confirm-email/<token>")
def confirm_email(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=86400)
    except SignatureExpired:
        flash("The verification link has expired.", "error")
        return redirect(url_for("login"))
    except BadTimeSignature:
        flash("Invalid verification link.", "error")
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    
    if user:
        db.execute("UPDATE users SET is_verified=1 WHERE email=?", (email,))
        db.commit()
        flash("Your email has been successfully verified! You can now log in.", "ok")
    else:
        flash("User not found.", "error")

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    unverified = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form.get("password", "")):
            if MAIL_CONFIGURED and user["role"] == "student" and not user["is_verified"]:
                flash("Please verify your email first. Check your inbox and spam folder.", "warn")
                unverified = email
            else:
                csrf = session.get("csrf")
                session.clear()
                session["csrf"] = csrf
                session["uid"] = user["id"]
                session.permanent = True
                nxt = request.args.get("next", "")
                if nxt.startswith("/") and not nxt.startswith("//"):
                    return redirect(nxt)
                return redirect(url_for("index"))
        else:
            flash("Email or password is incorrect.", "error")
    return render_template("login.html", unverified_email=unverified)


@app.route("/resend-verification", methods=["POST"])
def resend_verification():
    email = request.form.get("email", "").strip().lower()
    user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if user and not user["is_verified"]:
        send_verification_email(user["email"], user["name"])
    flash("If that account needs verifying, we have sent a new link.", "ok")
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Student pages
# ---------------------------------------------------------------------------
def doc_progress(uid):
    rows = get_db().execute("SELECT * FROM documents WHERE user_id=?", (uid,)).fetchall()
    return {r["doc_key"]: r for r in rows}


def upcoming_events(limit=None):
    cutoff = (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")
    sql = """SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id) AS taken
             FROM events e WHERE starts >= ? ORDER BY starts"""
    if limit:
        sql += f" LIMIT {int(limit)}"
    return get_db().execute(sql, (cutoff,)).fetchall()


@app.route("/dashboard")
@login_required
def dashboard():
    by_key = doc_progress(g.user["id"])
    approved = sum(1 for r in by_key.values() if r["status"] == "approved")
    next_doc = next((d for d in REQUIRED_DOCS if d["key"] not in by_key), None)
    db = get_db()
    place = db.execute("SELECT * FROM locations WHERE slug=?", (next_doc["place"],)).fetchone() if next_doc else None
    ann = db.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 2").fetchall()
    mine = {r["event_id"] for r in db.execute("SELECT event_id FROM registrations WHERE user_id=?", (g.user["id"],))}
    ticks = db.execute("SELECT COUNT(*) n FROM checklist WHERE user_id=?", (g.user["id"],)).fetchone()["n"]
    return render_template("dashboard.html", done=len(by_key), approved=approved, total=len(REQUIRED_DOCS),
                           next_doc=next_doc, place=place, announcements=ann, events=upcoming_events(3),
                           mine=mine, ticks=ticks, checklist_total=len(CHECKLIST))


@app.route("/registration", methods=["GET", "POST"])
@login_required
def documents():
    if request.method == "POST":
        key, file = request.form.get("doc_key"), request.files.get("file")
        if key not in {d["key"] for d in REQUIRED_DOCS}:
            abort(400)
        if not file or not file.filename:
            flash("Choose a file before uploading.", "error")
        elif not allowed(file.filename, DOC_EXT):
            flash("Only PDF, JPG or PNG files are accepted.", "error")
        else:
            ext = file.filename.rsplit(".", 1)[1].lower()
            stored = f"{g.user['id']}_{key}_{uuid.uuid4().hex[:8]}.{ext}"
            db = get_db()
            old = db.execute("SELECT filename FROM documents WHERE user_id=? AND doc_key=?", (g.user["id"], key)).fetchone()
            stored = store_file(file, UPLOADS, stored)
            db.execute("""INSERT INTO documents(user_id,doc_key,filename,original,status,uploaded_at) VALUES(?,?,?,?, 'pending', ?)
                          ON CONFLICT(user_id,doc_key) DO UPDATE SET filename=excluded.filename, original=excluded.original,
                          status='pending', note=NULL, uploaded_at=excluded.uploaded_at""",
                       (g.user["id"], key, stored, secure_filename(file.filename), now()))
            db.commit()
            if old:
                delete_file(UPLOADS, old["filename"])
            flash("Uploaded. The Registrar's office will review it.", "ok")
        return redirect(url_for("documents") + "#" + (key or ""))
    by_key = doc_progress(g.user["id"])
    places = {r["slug"]: r for r in get_db().execute("SELECT * FROM locations")}
    return render_template("documents.html", docs=REQUIRED_DOCS, by_key=by_key, places=places,
                           done=len(by_key), approved=sum(1 for r in by_key.values() if r["status"] == "approved"))


@app.route("/files/doc/<int:doc_id>")
@login_required
def doc_file(doc_id):
    d = get_db().execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not d or (d["user_id"] != g.user["id"] and g.user["role"] != "admin"):
        abort(404)
    return serve_file(UPLOADS, d["filename"])


@app.route("/map")
@login_required
def campus_map():
    return render_template("map.html")


@app.route("/api/places")
@login_required
def api_places():
    return jsonify([dict(r) for r in get_db().execute("SELECT * FROM locations")])


@app.route("/stay")
@login_required
def hotels():
    return render_template("hotels.html")


@app.route("/events")
@login_required
def events():
    cat = request.args.get("cat", "")
    db = get_db()
    rows = [e for e in upcoming_events() if not cat or e["category"] == cat]
    mine = {r["event_id"] for r in db.execute("SELECT event_id FROM registrations WHERE user_id=?", (g.user["id"],))}
    return render_template("events.html", events=rows, mine=mine, cat=cat, cats=EVENT_CATEGORIES)


@app.route("/events/<int:eid>/register", methods=["POST"])
@login_required
def event_register(eid):
    db = get_db()
    e = db.execute("SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id) AS taken FROM events e WHERE id=?", (eid,)).fetchone()
    if not e:
        abort(404)
    if request.form.get("action") == "cancel":
        db.execute("DELETE FROM registrations WHERE event_id=? AND user_id=?", (eid, g.user["id"]))
        flash("Your spot has been released.", "ok")
    elif e["capacity"] and e["taken"] >= e["capacity"]:
        flash("Sorry, this event is full.", "error")
    else:
        try:
            db.execute("INSERT INTO registrations(event_id,user_id,created) VALUES(?,?,?)", (eid, g.user["id"], now()))
            flash(f"You're registered for {e['title']}. See you there!", "ok")
        except DB_INTEGRITY:

            db.rollback()
            flash("You are already registered for this event.", "warn")
    db.commit()
    return redirect(request.referrer or url_for("events"))


@app.route("/community", methods=["GET", "POST"])
@login_required
def community():
    db = get_db()
    if request.method == "POST":
        f = request.form
        link = f.get("link", "").strip()
        if not f.get("name", "").strip() or not link.startswith("https://chat.whatsapp.com/"):
            flash("Add a group name and a WhatsApp invite link that starts with https://chat.whatsapp.com/", "error")
        else:
            cat = f.get("category") if f.get("category") in GROUP_CATEGORIES else GROUP_CATEGORIES[0]
            db.execute("INSERT INTO groups(name,category,link,description,added_by,status,created) VALUES(?,?,?,?,?,'pending',?)",
                       (f["name"].strip(), cat, link, f.get("description", "").strip(), g.user["id"], now()))
            db.commit()
            flash("Thanks! An admin will check your group and publish it.", "ok")
        return redirect(url_for("community") + "#suggest")
    rows = db.execute("SELECT * FROM groups WHERE status='approved' ORDER BY category, name").fetchall()
    pending = db.execute("SELECT * FROM groups WHERE status='pending' AND added_by=?", (g.user["id"],)).fetchall()
    grouped = {c: [r for r in rows if r["category"] == c] for c in GROUP_CATEGORIES}
    return render_template("community.html", grouped=grouped, pending=pending, cats=GROUP_CATEGORIES)


@app.route("/papers")
@login_required
def papers():
    q, course = request.args.get("q", "").strip(), request.args.get("course", "").strip()
    sql, args = "SELECT * FROM papers WHERE 1=1", []
    if q:
        sql += " AND (LOWER(title) LIKE LOWER(?) OR LOWER(unit_code) LIKE LOWER(?))"
        args += [f"%{q}%", f"%{q}%"]
    if course:
        sql += " AND course=?"
        args.append(course)
    db = get_db()
    rows = db.execute(sql + " ORDER BY year DESC, title", args).fetchall()
    courses = [r[0] for r in db.execute("SELECT DISTINCT course FROM papers ORDER BY course")]
    return render_template("papers.html", papers=rows, courses=courses, q=q, course=course)


@app.route("/files/paper/<int:pid>")
@login_required
def paper_file(pid):
    p = get_db().execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
    if not p:
        abort(404)
    return serve_file(PAPERS, p["filename"], True, p["original"])


@app.route("/guide")
@login_required
def guide():
    done = {r["item"] for r in get_db().execute("SELECT item FROM checklist WHERE user_id=?", (g.user["id"],))}
    return render_template("guide.html", checklist=CHECKLIST, done=done, tips=TIPS)


@app.route("/guide/toggle", methods=["POST"])
@login_required
def guide_toggle():
    item = (request.get_json(silent=True) or {}).get("item")
    if item not in {k for k, _ in CHECKLIST}:
        abort(400)
    db = get_db()
    if db.execute("SELECT 1 FROM checklist WHERE user_id=? AND item=?", (g.user["id"], item)).fetchone():
        db.execute("DELETE FROM checklist WHERE user_id=? AND item=?", (g.user["id"], item))
        on = False
    else:
        db.execute("INSERT INTO checklist(user_id,item) VALUES(?,?)", (g.user["id"], item))
        on = True
    db.commit()
    n = db.execute("SELECT COUNT(*) n FROM checklist WHERE user_id=?", (g.user["id"],)).fetchone()["n"]
    return jsonify(on=on, count=n, total=len(CHECKLIST))


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
ADMIN_TABS = [("overview", "Overview"), ("students", "Students"), ("documents", "Documents"),
              ("events", "Events"), ("groups", "WhatsApp groups"), ("papers", "Revision papers"), ("places", "Map places")]


@app.route("/admin")
@admin_required
def admin():
    return redirect(url_for("admin_tab", tab="overview"))


@app.route("/admin/<tab>")
@admin_required
def admin_tab(tab):
    if tab not in dict(ADMIN_TABS):
        abort(404)
    db = get_db()
    ctx = {"tab": tab, "tabs": ADMIN_TABS, "event_cats": EVENT_CATEGORIES, "group_cats": GROUP_CATEGORIES}
    if tab == "overview":
        ctx.update(
            n_students=db.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()["n"],
            n_pending=db.execute("SELECT COUNT(*) n FROM documents WHERE status='pending'").fetchone()["n"],
            n_regs=db.execute("SELECT COUNT(*) n FROM registrations").fetchone()["n"],
            n_groups=db.execute("SELECT COUNT(*) n FROM groups WHERE status='pending'").fetchone()["n"],
            announcements=db.execute("SELECT * FROM announcements ORDER BY id DESC").fetchall())
    elif tab == "students":
        ctx["students"] = db.execute("SELECT * FROM users WHERE role='student' ORDER BY created DESC").fetchall()
        ctx["counts"] = {r["user_id"]: r["n"] for r in db.execute("SELECT user_id, COUNT(*) n FROM documents GROUP BY user_id")}
        ctx["total"] = len(REQUIRED_DOCS)
    elif tab == "documents":
        ctx["docs"] = db.execute("""SELECT d.*, u.name AS student FROM documents d JOIN users u ON u.id=d.user_id
            ORDER BY CASE d.status WHEN 'pending' THEN 0 ELSE 1 END, d.uploaded_at DESC""").fetchall()
        ctx["titles"] = {d["key"]: d["title"] for d in REQUIRED_DOCS}
    elif tab == "events":
        ctx["events"] = db.execute("""SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id) AS taken
                                      FROM events e ORDER BY starts""").fetchall()
    elif tab == "groups":
        ctx["groups"] = db.execute("""SELECT gr.*, u.name AS who FROM groups gr LEFT JOIN users u ON u.id=gr.added_by
            ORDER BY CASE gr.status WHEN 'pending' THEN 0 ELSE 1 END, gr.created DESC""").fetchall()
    elif tab == "papers":
        ctx["papers"] = db.execute("SELECT * FROM papers ORDER BY uploaded_at DESC").fetchall()
    elif tab == "places":
        ctx["places"] = db.execute("SELECT * FROM locations ORDER BY category, name").fetchall()
    return render_template("admin.html", **ctx)


def back(tab):
    return redirect(url_for("admin_tab", tab=tab))


@app.route("/admin/announce", methods=["POST"])
@admin_required
def admin_announce():
    f = request.form
    if f.get("title", "").strip():
        get_db().execute("INSERT INTO announcements(title,body,created) VALUES(?,?,?)", (f["title"].strip(), f.get("body", "").strip(), now()))
        get_db().commit()
        flash("Announcement posted.", "ok")
    return back("overview")


@app.route("/admin/announce/<int:aid>/delete", methods=["POST"])
@admin_required
def admin_announce_delete(aid):
    get_db().execute("DELETE FROM announcements WHERE id=?", (aid,))
    get_db().commit()
    return back("overview")


@app.route("/admin/review/<int:doc_id>", methods=["POST"])
@admin_required
def admin_review(doc_id):
    status = request.form.get("status")
    if status not in ("approved", "rejected"):
        abort(400)
    get_db().execute("UPDATE documents SET status=?, note=? WHERE id=?", (status, request.form.get("note", "").strip(), doc_id))
    get_db().commit()
    flash(f"Document marked {status}.", "ok")
    return back("documents")


@app.route("/admin/events/add", methods=["POST"])
@admin_required
def admin_event_add():
    f = request.form
    try:
        starts = datetime.strptime(f.get("date", "") + " " + f.get("time", ""), "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")
    except ValueError:
        flash("Pick a valid date and time.", "error")
        return back("events")
    if not f.get("title", "").strip():
        flash("Give the event a title.", "error")
        return back("events")
    cat = f.get("category") if f.get("category") in EVENT_CATEGORIES else EVENT_CATEGORIES[0]
    get_db().execute("INSERT INTO events(title,description,category,starts,venue,capacity,created) VALUES(?,?,?,?,?,?,?)",
                     (f["title"].strip(), f.get("description", "").strip(), cat, starts, f.get("venue", "").strip(),
                      int(f.get("capacity") or 0), now()))
    get_db().commit()
    flash("Event added.", "ok")
    return back("events")


@app.route("/admin/events/<int:eid>/delete", methods=["POST"])
@admin_required
def admin_event_delete(eid):
    db = get_db()
    db.execute("DELETE FROM registrations WHERE event_id=?", (eid,))
    db.execute("DELETE FROM events WHERE id=?", (eid,))
    db.commit()
    return back("events")


@app.route("/admin/groups/add", methods=["POST"])
@admin_required
def admin_group_add():
    f = request.form
    link = f.get("link", "").strip()
    if not f.get("name", "").strip() or not link.startswith("https://chat.whatsapp.com/"):
        flash("Add a name and a link starting with https://chat.whatsapp.com/", "error")
        return back("groups")
    cat = f.get("category") if f.get("category") in GROUP_CATEGORIES else GROUP_CATEGORIES[0]
    get_db().execute("INSERT INTO groups(name,category,link,description,added_by,status,created) VALUES(?,?,?,?,?,'approved',?)",
                     (f["name"].strip(), cat, link, f.get("description", "").strip(), g.user["id"], now()))
    get_db().commit()
    flash("Group published.", "ok")
    return back("groups")


@app.route("/admin/groups/<int:gid>/<action>", methods=["POST"])
@admin_required
def admin_group_action(gid, action):
    db = get_db()
    if action == "approve":
        db.execute("UPDATE groups SET status='approved' WHERE id=?", (gid,))
    elif action == "delete":
        db.execute("DELETE FROM groups WHERE id=?", (gid,))
    else:
        abort(400)
    db.commit()
    return back("groups")


@app.route("/admin/papers/add", methods=["POST"])
@admin_required
def admin_add_paper():
    f, file = request.form, request.files.get("file")
    if not file or not file.filename or not allowed(file.filename, PAPER_EXT) or not f.get("title", "").strip():
        flash("Add a title and a PDF, Word or PowerPoint file.", "error")
        return back("papers")
    stored = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
    stored = store_file(file, PAPERS, stored)
    get_db().execute("INSERT INTO papers(title,course,unit_code,year,filename,original,uploaded_at) VALUES(?,?,?,?,?,?,?)",
                     (f["title"].strip(), f.get("course", "").strip() or "General", f.get("unit_code", "").strip(),
                      f.get("year", "").strip(), stored, secure_filename(file.filename), now()))
    get_db().commit()
    flash("Revision paper added.", "ok")
    return back("papers")


@app.route("/admin/papers/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_delete_paper(pid):
    db = get_db()
    p = db.execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
    if p:
        delete_file(PAPERS, p["filename"])
        db.execute("DELETE FROM papers WHERE id=?", (pid,))
        db.commit()
    return back("papers")


@app.route("/admin/places/<int:pid>/pin", methods=["POST"])
@admin_required
def admin_place_pin(pid):
    try:
        lat, lng = float(request.form["lat"]), float(request.form["lng"])
    except (KeyError, ValueError):
        flash("Latitude and longitude must be numbers, for example -0.0048 and 34.6005.", "error")
        return back("places")
    get_db().execute("UPDATE locations SET lat=?, lng=?, verified=1 WHERE id=?", (lat, lng, pid))
    get_db().commit()
    flash("Pin saved. The map will now always use these coordinates.", "ok")
    return back("places")


@app.route("/admin/places/add", methods=["POST"])
@admin_required
def admin_place_add():
    f = request.form
    try:
        lat, lng = float(f["lat"]), float(f["lng"])
    except (KeyError, ValueError):
        flash("Latitude and longitude must be numbers.", "error")
        return back("places")
    name = f.get("name", "").strip()
    if not name:
        flash("Give the place a name.", "error")
        return back("places")
    get_db().execute("INSERT INTO locations(slug,name,category,query,lat,lng,description,verified) VALUES(?,?,?,?,?,?,?,1)",
                     (uuid.uuid4().hex[:8], name, f.get("category", "lecture"), name + " Maseno University", lat, lng,
                      f.get("description", "").strip()))
    get_db().commit()
    flash("Place added to the map.", "ok")
    return back("places")


@app.route("/admin/places/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_place_delete(pid):
    get_db().execute("DELETE FROM locations WHERE id=?", (pid,))
    get_db().commit()
    return back("places")


init_db()

if __name__ == "__main__":
    app.run(debug=not config.PRODUCTION)