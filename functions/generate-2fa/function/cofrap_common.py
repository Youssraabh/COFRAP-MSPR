"""COFRAP — code partagé par les fonctions serverless.

Regroupe l'accès base de données, la crypto (bcrypt + Fernet), la génération
de mot de passe et la fabrication de QR codes. Conçu pour être testable hors
cluster (les dépendances réseau ne sont touchées qu'à l'appel des fonctions DB).
"""
import base64
import os
import secrets
import string
import time
from io import BytesIO

import bcrypt
import pyotp
import qrcode
from cryptography.fernet import Fernet

# 6 mois ~ 182 jours.
SIX_MONTHS_SECONDS = 182 * 24 * 3600
PASSWORD_LENGTH = 24


# --------------------------------------------------------------------------- #
# Mot de passe
# --------------------------------------------------------------------------- #
def generate_password(length: int = PASSWORD_LENGTH) -> str:
    """Mot de passe robuste : >=1 majuscule, minuscule, chiffre, spécial."""
    specials = "!@#$%^&*()-_=+"
    pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, specials]
    alphabet = "".join(pools)
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(c in pool for c in pwd) for pool in pools):
            return pwd


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# Chiffrement du secret 2FA (réversible : on doit pouvoir vérifier le TOTP)
# --------------------------------------------------------------------------- #
def _fernet() -> Fernet:
    key = _read_secret("totp-encryption-key", os.getenv("COFRAP_FERNET_KEY", ""))
    if not key:
        raise RuntimeError("totp-encryption-key manquant (secret OpenFaaS).")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# --------------------------------------------------------------------------- #
# 2FA TOTP
# --------------------------------------------------------------------------- #
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(username: str, secret: str, issuer: str = "COFRAP") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(str(code), valid_window=1)


# --------------------------------------------------------------------------- #
# QR code
# --------------------------------------------------------------------------- #
def qr_png_base64(data: str) -> str:
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# --------------------------------------------------------------------------- #
# Expiration
# --------------------------------------------------------------------------- #
def now_epoch() -> int:
    return int(time.time())


def is_expired(gendate, ttl: int = SIX_MONTHS_SECONDS) -> bool:
    if gendate is None:
        return True
    return (now_epoch() - int(gendate)) > ttl


# --------------------------------------------------------------------------- #
# Base de données
# --------------------------------------------------------------------------- #
def get_conn():
    import psycopg2

    return psycopg2.connect(
        host=_read_secret("db-host", os.getenv("DB_HOST", "postgresql")),
        port=int(_read_secret("db-port", os.getenv("DB_PORT", "5432"))),
        dbname=_read_secret("db-name", os.getenv("DB_NAME", "cofrap")),
        user=_read_secret("db-user", os.getenv("DB_USER", "cofrap")),
        password=_read_secret("db-password", os.getenv("DB_PASSWORD", "cofrap")),
        connect_timeout=5,
    )


def _read_secret(name: str, default: str = "") -> str:
    """Secret OpenFaaS monté en fichier, sinon valeur par défaut."""
    path = f"/var/openfaas/secrets/{name}"
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return default


def upsert_password(username: str, password_hash: str, gendate: int) -> None:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (username, password, gendate, expired)
                VALUES (%s, %s, %s, 0)
                ON CONFLICT (username)
                DO UPDATE SET password = EXCLUDED.password,
                              gendate = EXCLUDED.gendate,
                              expired = 0
                """,
                (username, password_hash, gendate),
            )
    finally:
        conn.close()


def update_mfa(username: str, mfa_encrypted: str, gendate: int) -> None:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET mfa=%s, gendate=%s, expired=0 WHERE username=%s",
                (mfa_encrypted, gendate, username),
            )
    finally:
        conn.close()


def fetch_user(username: str):
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password, mfa, gendate, expired "
                "FROM users WHERE username=%s",
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def user_exists(username: str) -> bool:
    return fetch_user(username) is not None


def mark_expired(username: str) -> None:
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET expired=1 WHERE username=%s", (username,))
    finally:
        conn.close()
