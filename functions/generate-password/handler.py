"""generate-password : crée/renouvelle le mot de passe d'un compte.

Entrée  : {"username": "michel.ranu"}
Sortie  : {"username", "password", "qrcode" (PNG base64 du mot de passe), "gendate"}
Effet   : stocke le hash bcrypt + gendate, expired=0.
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

    password = cc.generate_password()
    gendate = cc.now_epoch()
    cc.upsert_password(username, cc.hash_password(password), gendate)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(
            {
                "username": username,
                "password": password,
                "qrcode": cc.qr_png_base64(password),
                "gendate": gendate,
            }
        ),
    }
