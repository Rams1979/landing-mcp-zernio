import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from common import campana
from common.config import hoy
from common.db import Base, Lead, engine, init_db, session
from landing.app import app
from mcp_server import server


@pytest.fixture(autouse=True)
def bd_limpia():
    Base.metadata.drop_all(engine)
    init_db()
    from landing import app as m
    m._intentos.clear()
    yield


def dia_valido():
    d = hoy() + timedelta(days=1)
    while d.weekday() not in campana.DIAS_RETIRO:
        d += timedelta(days=1)
    return d.isoformat()


def reservar(c, **kw):
    datos = {"nombre": "Ana Mora", "whatsapp": "8888 0000", "dia": dia_valido(), "espacio": "poca_luz", **kw}
    return c.post("/reservar", data=datos, follow_redirects=False)


def test_flujo_feliz_y_cupos():
    with TestClient(app) as c:
        r = reservar(c)
        assert r.status_code == 303 and r.headers["location"].startswith("/gracias")
        assert "Quedan" in c.get("/").text
    with session() as s:
        assert s.query(Lead).count() == 1


def test_validaciones():
    with TestClient(app) as c:
        assert reservar(c, whatsapp="123").status_code == 422
        assert reservar(c, nombre="A").status_code == 422
        assert reservar(c, espacio="x").status_code == 422
        assert reservar(c, dia="2020-01-01").status_code == 422
        assert reservar(c, dia="basura").status_code == 422


def test_duplicado_y_honeypot():
    with TestClient(app) as c:
        assert reservar(c).status_code == 303
        assert reservar(c).status_code == 422
        assert reservar(c, web="spam", whatsapp="8777 1111").headers["location"] == "/"
    with session() as s:
        assert s.query(Lead).count() == 1


def test_cupo_lleno():
    with TestClient(app) as c:
        for i in range(campana.CUPOS_POR_DIA):
            assert reservar(c, whatsapp=f"8000 00{i:02d}").status_code == 303
            c.app  # sin límite por IP en este test
            from landing import app as m
            m._intentos.clear()
        r = reservar(c, whatsapp="8999 9999")
        assert r.status_code == 422


def test_rate_limit():
    with TestClient(app) as c:
        codigos = [reservar(c, whatsapp=f"8111 {i:04d}", nombre="x").status_code for i in range(8)]
        assert 429 in codigos


def test_mcp_herramientas():
    with TestClient(app) as c:
        reservar(c)
    async def run():
        async with Client(server.mcp) as cl:
            nombres = {t.name for t in await cl.list_tools()}
            assert nombres == {"estado_campana", "cupos_por_dia", "listar_leads", "resumen_campana"}
            est = (await cl.call_tool("estado_campana", {})).data
            assert est["leads_totales"] == 1
            leads = (await cl.call_tool("listar_leads", {})).data
            assert leads[0]["whatsapp"] == "****0000" and leads[0]["nombre"] == "Ana M."
            cupos = (await cl.call_tool("cupos_por_dia", {"dias": 7, "solo_con_cupo": True})).data
            assert cupos and all(x["libres"] > 0 for x in cupos)
            res = (await cl.call_tool("resumen_campana", {})).data
            assert res["espacios_mas_pedidos"] == {"Poca luz": 1}
    asyncio.run(run())


def test_mcp_auth_http():
    t = "t" * 32
    with TestClient(server.crear_app()) as h:
        assert h.get("/health").status_code == 200
        assert h.get("/").status_code == 200
        assert h.get("/.well-known/oauth-authorization-server").status_code == 404
        assert h.post("/mcp", json={}).status_code == 401
        assert h.post("/mcp", json={}, headers={"Authorization": "Bearer mal"}).status_code == 401
        assert h.post("/mcp?key=mal", json={}).status_code == 401
        assert h.post("/mcp", json={}, headers={"Authorization": f"Bearer {t}"}).status_code != 401
        assert h.post(f"/mcp?key={t}", json={}).status_code != 401


def test_sin_token_no_arranca(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "")
    with pytest.raises(RuntimeError):
        server.crear_app()
