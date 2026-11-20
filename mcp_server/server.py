"""Servidor MCP (solo lectura) con los datos de la campaña. Transporte HTTP en /mcp."""
import hmac
import os
from datetime import date, timedelta

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from common import campana, service
from common.config import hoy
from common.db import init_db, session

LECTURA = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

mcp = FastMCP(
    "Campaña " + campana.NEGOCIO,
    instructions=(
        f"Datos de la campaña '{campana.OFERTA}' de {campana.NEGOCIO} (demo con cifras ficticias). "
        "Usa estas herramientas para conocer cupos y leads antes de proponer una publicación. "
        "Los teléfonos vienen enmascarados: nunca los pidas ni los publiques."
    ),
)


def _dia(d: dict) -> dict:
    f = d["fecha"]
    return {"fecha": f.isoformat(), "dia": campana.fecha_larga(f), **{k: d[k] for k in ("total", "ocupados", "libres")}}


@mcp.tool(annotations=LECTURA)
def estado_campana() -> dict:
    """Estado general: oferta, precios, días restantes, cupos ocupados/libres y total de leads."""
    with session() as s:
        e = service.estado(s)
    return {
        "negocio": campana.NEGOCIO, "oferta": campana.OFERTA, "contenido": campana.DESCRIPCION,
        "precio_ancla": campana.colones(campana.PRECIO_ANCLA), "precio_oferta": campana.colones(campana.PRECIO_OFERTA),
        "fecha_limite": campana.fecha_larga(campana.FECHA_LIMITE), "hoy": hoy().isoformat(), **e,
    }


@mcp.tool(annotations=LECTURA)
def cupos_por_dia(dias: int = 14, solo_con_cupo: bool = False) -> list[dict]:
    """Cupos por día de retiro desde hoy. `dias` = cuántos días hacia adelante (1 a 60);
    `solo_con_cupo` = omite días llenos."""
    dias = max(1, min(dias, 60))
    with session() as s:
        filas = service.cupos_por_dia(s, hasta=hoy() + timedelta(days=dias - 1))
    return [_dia(d) for d in filas if d["libres"] > 0 or not solo_con_cupo]


@mcp.tool(annotations=LECTURA)
def listar_leads(limite: int = 20, dia: str | None = None) -> list[dict]:
    """Últimos leads, del más reciente al más antiguo (máx. 100). Nombre abreviado y WhatsApp enmascarado.
    `dia` opcional en formato AAAA-MM-DD para filtrar por día de retiro."""
    try:
        fecha = date.fromisoformat(dia) if dia else None
    except ValueError:
        raise ValueError("`dia` debe tener formato AAAA-MM-DD, por ejemplo 2026-12-15")
    with session() as s:
        return service.listar_leads(s, limite, fecha)


@mcp.tool(annotations=LECTURA)
def resumen_campana() -> dict:
    """Resumen listo para redactar una publicación: avance, días más vacíos y llenos, y tipo de espacio más común."""
    with session() as s:
        e = service.estado(s)
        futuros = [d for d in service.cupos_por_dia(s) if d["libres"] > 0]
        espacios = service.distribucion_espacios(s)
    vacios = sorted(futuros, key=lambda d: (-d["libres"], d["fecha"]))[:3]
    casi_llenos = sorted((d for d in futuros if d["ocupados"] > 0), key=lambda d: (d["libres"], d["fecha"]))[:3]
    return {
        "oferta": campana.OFERTA, "precio_oferta": campana.colones(campana.PRECIO_OFERTA),
        "precio_ancla": campana.colones(campana.PRECIO_ANCLA),
        "fecha_limite": campana.fecha_larga(campana.FECHA_LIMITE),
        "cupos_libres": e["cupos_libres_desde_hoy"], "ocupacion_pct": e["ocupacion_pct"],
        "dias_restantes": e["dias_restantes"],
        "dias_con_mas_cupo": [_dia(d) for d in vacios],
        "dias_casi_llenos": [_dia(d) for d in casi_llenos],
        "espacios_mas_pedidos": espacios,
    }


class AuthToken:
    """Middleware ASGI. El secreto viaja en la URL: `/<MCP_TOKEN>/mcp`.

    Claude (conectores personalizados) no puede enviar cabeceras propias y trata cualquier 401 como
    "este servidor usa OAuth". Por eso una petición sin credencial válida recibe 404, no 401.
    También se acepta `Authorization: Bearer` y `?key=` para clientes programáticos.
    /health y / quedan abiertos (sin datos).
    """

    def __init__(self, app, token: str):
        self.app, self.token = app, token.encode()

    def _ok(self, valor: bytes) -> bool:
        return bool(valor) and hmac.compare_digest(valor, self.token)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in ("/", "/health"):
            return await self.app(scope, receive, send)
        ruta = scope["path"]
        partes = ruta.split("/", 2)  # ["", "<segmento>", "<resto>"]
        if len(partes) == 3 and self._ok(partes[1].encode()):
            nueva = "/" + partes[2]
            scope = dict(scope, path=nueva, raw_path=nueva.encode())
            return await self.app(scope, receive, send)
        auth = dict(scope["headers"]).get(b"authorization", b"")
        if auth[:7].lower() == b"bearer " and self._ok(auth[7:].strip()):
            return await self.app(scope, receive, send)
        from urllib.parse import parse_qs
        if self._ok(parse_qs(scope["query_string"].decode()).get("key", [""])[0].encode()):
            return await self.app(scope, receive, send)
        resp = JSONResponse({"error": "no encontrado"}, status_code=404)
        await resp(scope, receive, send)


def crear_app():
    token = os.environ.get("MCP_TOKEN", "").strip()
    if len(token) < 24:
        raise RuntimeError("MCP_TOKEN no está definido o es demasiado corto (mínimo 24 caracteres).")
    init_db()
    app = mcp.http_app(path="/mcp")
    app.add_route("/health", lambda request: JSONResponse({"ok": True}))
    app.add_route("/", lambda request: JSONResponse({"servicio": "mcp", "endpoint": "/mcp"}))
    app.add_middleware(AuthToken, token=token)
    return app


def main():
    import uvicorn
    uvicorn.run(crear_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
