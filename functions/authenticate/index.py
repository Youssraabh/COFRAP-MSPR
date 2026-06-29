"""Point d'entrée HTTP pour of-watchdog (mode http, port 5000)."""
from flask import Flask, request, Response
from function.handler import handle

app = Flask(__name__)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def main_route(path=""):
    class _Ev:
        body = request.get_data()
        headers = dict(request.headers)
        method = request.method
        query = dict(request.args)

    class _Ctx:
        pass

    result = handle(_Ev(), _Ctx())
    status = result.get("statusCode", 200)
    body = result.get("body", "")
    hdrs = result.get("headers", {"Content-Type": "application/json"})
    return Response(body, status=status, headers=hdrs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
