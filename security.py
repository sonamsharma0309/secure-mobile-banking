import os
import secrets
from cryptography.fernet import Fernet

INSTANCE_DIR = "instance"
SECRET_KEY_PATH = os.path.join(INSTANCE_DIR, "secret_key.txt")
ENC_KEY_PATH = os.path.join(INSTANCE_DIR, "enc_key.key")

def ensure_instance_dir():
    os.makedirs(INSTANCE_DIR, exist_ok=True)

def load_or_create_secret_key() -> str:
    ensure_instance_dir()
    if os.path.exists(SECRET_KEY_PATH):
        return open(SECRET_KEY_PATH, "r", encoding="utf-8").read().strip()
    key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(key)
    return key

def load_or_create_fernet() -> Fernet:
    ensure_instance_dir()
    if os.path.exists(ENC_KEY_PATH):
        key = open(ENC_KEY_PATH, "rb").read().strip()
        return Fernet(key)
    key = Fernet.generate_key()
    with open(ENC_KEY_PATH, "wb") as f:
        f.write(key)
    return Fernet(key)

# ---------- CSRF ----------
def make_csrf_token(session) -> str:
    token = secrets.token_urlsafe(32)
    session["csrf_token"] = token
    return token

def validate_csrf(session, token_from_form: str) -> bool:
    token = session.get("csrf_token")
    if not token or not token_from_form:
        return False
    return secrets.compare_digest(token, token_from_form)
