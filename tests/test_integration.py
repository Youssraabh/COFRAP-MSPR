"""Test d'intégration end-to-end : DB en mémoire, parcours complet du sujet.

création → QR mot de passe + 2FA → authentification OK → expiration → renew → OK.
La base PostgreSQL est remplacée par un dict mémoire (pas de cluster requis).
"""
import json
from types import SimpleNamespace

import pyotp

import cofrap_common as cc
import handler_password
import handler_2fa
import handler_auth


class FakeDB:
    """Implémente le contrat DB de cofrap_common, en mémoire."""

    def __init__(self):
        self.rows = {}

    def upsert_password(self, username, pwd_hash, gendate):
        self.rows[username] = [None, username, pwd_hash, "", gendate, 0]

    def update_mfa(self, username, mfa, gendate):
        self.rows[username][3] = mfa
        self.rows[username][4] = gendate
        self.rows[username][5] = 0

    def fetch_user(self, username):
        r = self.rows.get(username)
        return tuple(r) if r else None

    def user_exists(self, username):
        return username in self.rows

    def mark_expired(self, username):
        self.rows[username][5] = 1


def _evt(payload):
    return SimpleNamespace(body=json.dumps(payload).encode())


def _secret_from_qr_capture(monkeypatch, db):
    captured = {}
    real_enc = cc.encrypt_secret

    def cap(secret):
        captured["s"] = secret
        return real_enc(secret)

    monkeypatch.setattr(cc, "encrypt_secret", cap)
    return captured


def test_full_journey(monkeypatch):
    db = FakeDB()
    for fn in ("upsert_password", "update_mfa", "fetch_user", "user_exists", "mark_expired"):
        monkeypatch.setattr(cc, fn, getattr(db, fn))
    captured = _secret_from_qr_capture(monkeypatch, db)

    # 1) Création : mot de passe + QR
    res = handler_password.handle(_evt({"username": "michel.ranu"}), None)
    pwd = json.loads(res["body"])["password"]
    assert len(pwd) == 24

    # 2) 2FA générée
    assert handler_2fa.handle(_evt({"username": "michel.ranu"}), None)["statusCode"] == 200
    code = pyotp.TOTP(captured["s"]).now()

    # 3) Auth OK
    r = handler_auth.handle(_evt({"username": "michel.ranu", "password": pwd, "totp_code": code}), None)
    assert json.loads(r["body"])["authenticated"] is True

    # 4) Expiration forcée (> 6 mois) → renew demandé
    db.rows["michel.ranu"][4] = cc.now_epoch() - cc.SIX_MONTHS_SECONDS - 1
    r = handler_auth.handle(_evt({"username": "michel.ranu", "password": pwd, "totp_code": code}), None)
    assert json.loads(r["body"])["expired"] is True

    # 5) Renouvellement → nouveau pwd + 2FA → auth OK
    pwd2 = json.loads(handler_password.handle(_evt({"username": "michel.ranu"}), None)["body"])["password"]
    handler_2fa.handle(_evt({"username": "michel.ranu"}), None)
    code2 = pyotp.TOTP(captured["s"]).now()
    r = handler_auth.handle(_evt({"username": "michel.ranu", "password": pwd2, "totp_code": code2}), None)
    assert json.loads(r["body"])["authenticated"] is True
