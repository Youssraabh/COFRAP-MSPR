"""Fixtures : clé Fernet de test, chemin module commun, chargement des handlers."""
import importlib.util
import os
import sys

from cryptography.fernet import Fernet

# Clé éphémère générée à chaque run : aucun secret n'est versionné.
os.environ.setdefault("COFRAP_FERNET_KEY", Fernet.generate_key().decode())

BASE = os.path.dirname(os.path.dirname(__file__))
# Module commun unique partagé par tous les handlers (cohérence du monkeypatch).
sys.path.insert(0, os.path.join(BASE, "functions", "common"))


def _load(alias, folder):
    path = os.path.join(BASE, "functions", folder, "handler.py")
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules[alias] = mod
    return mod


_load("handler_password", "generate-password")
_load("handler_2fa", "generate-2fa")
_load("handler_auth", "authenticate")
