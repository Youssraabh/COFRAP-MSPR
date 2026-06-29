"""Tests des trois fonctions OpenFaaS (DB mockée)."""
import json
from types import SimpleNamespace

import cofrap_common as cc
import handler_password
import handler_2fa
import handler_auth


def _evt(payload):
    return SimpleNamespace(body=json.dumps(payload).encode())


def test_generate_password(monkeypatch):
    saved = {}
    monkeypatch.setattr(cc, "upsert_password", lambda u, h, g: saved.update(u=u, h=h, g=g))
    res = handler_password.handle(_evt({"username": "michel.ranu"}), None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200
    assert len(body["password"]) == 24
    assert body["qrcode"] and cc.verify_password(body["password"], saved["h"])


def test_generate_password_requires_username():
    res = handler_password.handle(_evt({}), None)
    assert res["statusCode"] == 400


def test_generate_2fa(monkeypatch):
    saved = {}
    monkeypatch.setattr(cc, "user_exists", lambda u: True)
    monkeypatch.setattr(cc, "update_mfa", lambda u, m, g: saved.update(u=u, m=m, g=g))
    res = handler_2fa.handle(_evt({"username": "michel.ranu"}), None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200 and body["qrcode"]
    assert cc.decrypt_secret(saved["m"])  # secret déchiffrable


def test_authenticate_success(monkeypatch):
    import pyotp
    secret = cc.generate_totp_secret()
    user = (1, "u", cc.hash_password("pw"), cc.encrypt_secret(secret), cc.now_epoch(), 0)
    monkeypatch.setattr(cc, "fetch_user", lambda u: user)
    res = handler_auth.handle(_evt({"username": "u", "password": "pw",
                                    "totp_code": pyotp.TOTP(secret).now()}), None)
    assert res["statusCode"] == 200
    assert json.loads(res["body"])["authenticated"] is True


def test_authenticate_expired(monkeypatch):
    user = (1, "u", "h", "m", 0, 0)
    monkeypatch.setattr(cc, "fetch_user", lambda u: user)
    monkeypatch.setattr(cc, "mark_expired", lambda u: None)
    res = handler_auth.handle(_evt({"username": "u", "password": "x", "totp_code": "1"}), None)
    body = json.loads(res["body"])
    assert res["statusCode"] == 200 and body["expired"] is True


def test_authenticate_not_found(monkeypatch):
    monkeypatch.setattr(cc, "fetch_user", lambda u: None)
    res = handler_auth.handle(_evt({"username": "u", "password": "x", "totp_code": "1"}), None)
    assert res["statusCode"] == 404


def test_generate_2fa_user_absent(monkeypatch):
    monkeypatch.setattr(cc, "user_exists", lambda u: False)
    res = handler_2fa.handle(_evt({"username": "ghost"}), None)
    assert res["statusCode"] == 404
