"""authenticate : vérifie login + mot de passe + code TOTP, contrôle expiration.

Entrée : {"username", "password", "totp_code"}
Sortie :
  - 200 {"authenticated": true, "expired": false}          identifiants valides
  - 200 {"authenticated": false, "expired": true, "renew": true}  > 6 mois -> expiré
  - 401 {"authenticated": false, "expired": false}         login/mdp/2FA invalide
  - 404 {"error": "not_found"}                             compte inexistant
  - 400 / 500                                              entrée / erreur DB
"""
import json

import cofrap_common as cc


def handle(event, context):
    try:
        body = json.loads(event.body or b"{}")
    except (ValueError, TypeError):
        return _json(400, {"error": "JSON invalide"})

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    # Accepte totp_code (contrat) ou otp (alias).
    totp_code = body.get("totp_code") or body.get("otp") or ""

    if not username or not password or not totp_code:
        return _json(400, {"error": "username, password et totp_code requis"})

    user = cc.fetch_user(username)
    if not user:
        return _json(404, {"error": "not_found"})

    _, _, pwd_hash, mfa_enc, gendate, expired = user

    if expired or cc.is_expired(gendate):
        cc.mark_expired(username)
        return _json(200, {"authenticated": False, "expired": True, "renew": True})

    pwd_ok = cc.verify_password(password, pwd_hash)
    totp_ok = bool(mfa_enc) and cc.verify_totp(cc.decrypt_secret(mfa_enc), totp_code)

    if pwd_ok and totp_ok:
        return _json(200, {"authenticated": True, "expired": False, "username": username})
    return _json(401, {"authenticated": False, "expired": False})


def _json(code, payload):
    return {
        "statusCode": code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }
