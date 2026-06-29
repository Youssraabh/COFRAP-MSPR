"""Tests du module partagé : mot de passe, crypto, TOTP, QR, expiration."""
import string

import cofrap_common as cc


def test_password_length_and_classes():
    pwd = cc.generate_password()
    assert len(pwd) == 24
    assert any(c in string.ascii_uppercase for c in pwd)
    assert any(c in string.ascii_lowercase for c in pwd)
    assert any(c in string.digits for c in pwd)
    assert any(not c.isalnum() for c in pwd)


def test_password_unique():
    assert cc.generate_password() != cc.generate_password()


def test_hash_and_verify():
    h = cc.hash_password("S3cret!")
    assert cc.verify_password("S3cret!", h)
    assert not cc.verify_password("wrong", h)


def test_encrypt_decrypt_roundtrip():
    token = cc.encrypt_secret("ABCDEF")
    assert token != "ABCDEF"
    assert cc.decrypt_secret(token) == "ABCDEF"


def test_totp_verify():
    import pyotp
    secret = cc.generate_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert cc.verify_totp(secret, code)
    assert not cc.verify_totp(secret, "000000")


def test_qr_base64():
    data = cc.qr_png_base64("hello")
    assert isinstance(data, str) and len(data) > 100


def test_expiration():
    assert cc.is_expired(0) is True
    assert cc.is_expired(cc.now_epoch()) is False
    assert cc.is_expired(None) is True
