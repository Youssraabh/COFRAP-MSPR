"""Frontend de démonstration COFRAP (FastAPI + Jinja2).

5 routes couvrant le parcours complet : accueil, création (mot de passe + 2FA),
connexion, renouvellement (compte expiré) et affichage des QR (usage unique).
Le frontend n'accède jamais à la base : il dialogue uniquement avec la gateway
OpenFaaS (OPENFAAS_URL). Architecture : Frontend ↔ OpenFaaS ↔ PostgreSQL.
"""
import os

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(__file__)
GATEWAY = os.getenv("OPENFAAS_URL", os.getenv("OPENFAAS_GATEWAY", "http://gateway.openfaas:8080"))

app = FastAPI(title="COFRAP — Démo authentification serverless")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


async def call_fn(name: str, payload: dict) -> tuple[int, dict]:
    url = f"{GATEWAY}/function/{name}"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json=payload)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"raw": r.text}


async def _generate_account(request: Request, username: str):
    """Crée/renouvelle un compte : generate-password puis generate-2fa."""
    _, pw = await call_fn("generate-password", {"username": username})
    _, mfa = await call_fn("generate-2fa", {"username": username})
    return templates.TemplateResponse(
        "qrcodes.html",
        {
            "request": request,
            "username": username,
            "password": pw.get("password"),
            "password_qr": pw.get("qrcode"),
            "mfa_qr": mfa.get("qrcode"),
        },
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/create", response_class=HTMLResponse)
async def create_form(request: Request):
    return templates.TemplateResponse("create.html", {"request": request})


@app.post("/create", response_class=HTMLResponse)
async def create(request: Request, username: str = Form(...)):
    return await _generate_account(request, username)


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(...),
):
    code, data = await call_fn(
        "authenticate",
        {"username": username, "password": password, "totp_code": totp_code},
    )
    if data.get("authenticated"):
        return templates.TemplateResponse("success.html", {"request": request, "username": username})
    if data.get("expired"):
        return templates.TemplateResponse("renew.html", {"request": request, "username": username})
    return templates.TemplateResponse(
        "result.html", {"request": request, "username": username, "code": code}
    )


@app.get("/renew", response_class=HTMLResponse)
async def renew_form(request: Request):
    return templates.TemplateResponse("renew.html", {"request": request, "username": ""})


@app.post("/renew", response_class=HTMLResponse)
async def renew(request: Request, username: str = Form(...)):
    return await _generate_account(request, username)


@app.get("/health")
async def health():
    return {"status": "ok"}
