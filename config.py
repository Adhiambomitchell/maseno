"""Settings. Secrets are read from environment variables or from a private .env file.

NEVER put real passwords or keys in this file. Copy .env.example to .env and fill it in.
"""
import os
import secrets
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

try:  # load .env from the project folder (works the same locally and on PythonAnywhere)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"))
except ImportError:
    pass


def _flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _secret_key():
    """Use SECRET_KEY from the environment, or create one once and keep it in .secret_key."""
    key = os.getenv("SECRET_KEY", "").strip()
    if key:
        return key
    path = os.path.join(BASE, ".secret_key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    if PRODUCTION:
        print("WARNING: SECRET_KEY is not set. Logins will reset on every restart. Set SECRET_KEY in your environment.", file=sys.stderr)
    key = secrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key)
    return key


# Database. Empty = SQLite file in the project folder (PythonAnywhere, local).
# On Render's free plan set DATABASE_URL to a Postgres connection string (e.g. from Neon),
# because Render's free filesystem is wiped on every restart.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Keep uploaded files inside the database (needed where the disk is wiped, like Render Free).
STORE_FILES_IN_DB = _flag("STORE_FILES_IN_DB", bool(DATABASE_URL))
# Free databases are small, so uploads are capped lower when stored in the database.
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "3" if STORE_FILES_IN_DB else "10"))

# Set PRODUCTION=1 in .env on PythonAnywhere (turns on secure cookies and turns off debug).
PRODUCTION = _flag("PRODUCTION")

SECRET_KEY = _secret_key()
CAMPUS_CENTER = {"lat": -0.0048, "lng": 34.6005}

# Admin account, created on first run. If ADMIN_PASSWORD is empty, a random one is generated
# and written to the error log once.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@maseno.ac.ke")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Geoapify (map tiles and nearby hotels). This key is visible in the browser by design,
# so restrict it to your site's address in the Geoapify dashboard.
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "")

# Email (verification links)
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USE_TLS = _flag("MAIL_USE_TLS", True)
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "") or MAIL_USERNAME

# Brevo sends email over HTTPS, so it works where SMTP ports are blocked (Render Free).
# MAIL_DEFAULT_SENDER must be an address you verified in Brevo.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")


class Config:
    SECRET_KEY = SECRET_KEY
    ADMIN_EMAIL = ADMIN_EMAIL
    ADMIN_PASSWORD = ADMIN_PASSWORD
    GEOAPIFY_API_KEY = GEOAPIFY_API_KEY
