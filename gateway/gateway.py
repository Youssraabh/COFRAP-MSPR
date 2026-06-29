"""
Local OpenFaaS gateway — développement sans cluster Kubernetes.
Route POST /function/{name} vers le handler Python correspondant.
"""
import importlib.util
import os
import sys
from pathlib import Path

from flask import Flask, request, Response

FUNCTIONS_DIR = Path(os.getenv("FUNCTIONS_DIR", "/functions"))
FUNCTION_NAMES = ["generate-password", "generate-2fa", "authenticate"]

app = Flask(__name__)
_handlers: dict = {}


def _load(fn_name: str):
    fn_root = str(FUNCTIONS_DIR / fn_name)
    # Ajoute la racine de la fonction au chemin pour que
    # 'from function import cofrap_common' fonctionne.
    if fn_root not in sys.path:
        sys.path.insert(0, fn_root)

    handler_path = FUNCTIONS_DIR / fn_name / "function" / "handler.py"
    mod_name = fn_name.replace("-", "_") + "_handler"
    spec = importlib.util.spec_from_file_location(mod_name, str(handler_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


for _name in FUNCTION_NAMES:
    try:
        _handlers[_name] = _load(_name)
        print(f"[gateway] charge : {_name}", flush=True)
    except Exception as exc:
        print(f"[gateway] ERREUR {_name}: {exc}", flush=True)


@app.route("/function/<fn_name>", methods=["GET", "POST"])
def call_function(fn_name: str):
    if fn_name not in _handlers:
        return Response('{"error":"fonction inconnue"}', status=404,
                        content_type="application/json")

    class _Ev:
        body = request.get_data()
        headers = dict(request.headers)
        method = request.method
        query = dict(request.args)

    class _Ctx:
        pass

    try:
        result = _handlers[fn_name].handle(_Ev(), _Ctx())
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return Response(f'{{"error":"{exc}"}}', status=500,
                        content_type="application/json")

    status = result.get("statusCode", 200)
    body = result.get("body", "")
    hdrs = result.get("headers", {"Content-Type": "application/json"})
    return Response(body, status=status, headers=hdrs)


@app.route("/healthz")
def health():
    return {"status": "ok", "functions": list(_handlers.keys())}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
