import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from common import campana, service
from common.config import hoy
from common.db import init_db, session

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
templates.env.globals.update(c=campana, colones=campana.colones, fecha_larga=campana.fecha_larga)


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

# Límite simple por IP en memoria: 6 envíos cada 10 minutos (por instancia).
_intentos: dict[str, deque] = defaultdict(deque)
VENTANA, MAX_INTENTOS = 600, 6


def _limitado(ip: str) -> bool:
    ahora = time.monotonic()
    q = _intentos[ip]
    while q and ahora - q[0] > VENTANA:
        q.popleft()
    if len(q) >= MAX_INTENTOS:
        return True
    q.append(ahora)
    return False


@app.middleware("http")
async def cabeceras(request: Request, call_next):
    r = await call_next(request)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["Referrer-Policy"] = "same-origin"
    r.headers["X-Frame-Options"] = "DENY"
    r.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; form-action 'self'")
    return r


def _contexto(request: Request, error: str | None = None, valores: dict | None = None) -> dict:
    with session() as s:
        dias = service.cupos_por_dia(s)
        est = service.estado(s)
    wa = os.environ.get("WHATSAPP_NEGOCIO", "").strip()
    return {
        "request": request, "dias": dias, "libres": est["cupos_libres_desde_hoy"],
        "vigente": est["oferta_vigente"], "restan": est["dias_restantes"],
        "error": error, "v": valores or {},
        "wa": f"https://wa.me/506{wa}" if wa.isdigit() and len(wa) == 8 else None,
    }


@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    return templates.TemplateResponse(request, "index.html", _contexto(request))


@app.post("/reservar", response_class=HTMLResponse)
def reservar(request: Request, nombre: str = Form(""), whatsapp: str = Form(""), dia: str = Form(""),
             espacio: str = Form(""), web: str = Form("")):
    if web:  # honeypot: un humano nunca llena este campo oculto
        return RedirectResponse("/", status_code=303)
    ip = request.client.host if request.client else "?"
    if _limitado(ip):
        return templates.TemplateResponse(request, "index.html", _contexto(
            request, "Demasiados intentos. Espere unos minutos e intente de nuevo."), status_code=429)
    valores = {"nombre": nombre, "whatsapp": whatsapp, "dia": dia, "espacio": espacio}
    try:
        with session() as s:
            fecha = service.registrar_lead(s, nombre, whatsapp, dia, espacio)
    except service.ErrorRegistro as e:
        return templates.TemplateResponse(request, "index.html", _contexto(request, str(e), valores), status_code=422)
    return RedirectResponse(f"/gracias?dia={fecha.isoformat()}", status_code=303)


@app.get("/gracias", response_class=HTMLResponse)
def gracias(request: Request, dia: str = ""):
    try:
        fecha = date.fromisoformat(dia)
    except ValueError:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "gracias.html", {"request": request, "fecha": fecha})


@app.get("/health")
def health():
    return {"ok": True}
