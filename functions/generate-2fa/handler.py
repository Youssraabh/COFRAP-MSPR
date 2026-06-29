"""generate-2fa : génère le secret TOTP d'un compte et son QR otpauth.

Entrée  : {"username": "michel.ranu"}
Sortie  : {"username", "qrcode" (PNG base64 otpauth), "gendate"}
Effet   : stocke le secret chiffré (Fernet), expired=0.
"""
import json

import cofrap_common as cc


def handle(event, context):
    try:
        body = json.loads(event.body or b"{}")
    except (ValueError, TypeError):
        return {"statusCode": 400, "body": "JSON invalide"}

    username = (body.get("username") or "").strip()
    if not username:
        return {"statusCode": 400, "body": json.dumps({"error": "username requis"})}

    if not cc.user_exists(username):
        return {"statusCode": 404, "body": json.dumps({"error": "compte inexistant"})}

    secret = cc.generate_totp_secret()
    gendate = cc.now_epoch()
    cc.update_mfa(username, cc.encrypt_secret(secret), gendate)
    uri = cc.totp_uri(username, secret)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "username": username,
                "qrcode": cc.qr_png_base64(uri),
                "gendate": gendate,
            }
        ),
    }
