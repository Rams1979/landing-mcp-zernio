"""Punto de entrada único para Railway (Railpack lo detecta sin configuración).

Un mismo repo, dos servicios:
  - landing (por defecto)
  - mcp     -> definir la variable SERVICE=mcp en ese servicio
"""
import os


def _crear_app():
    if os.environ.get("SERVICE", "landing").strip().lower() == "mcp":
        from mcp_server.server import crear_app
        return crear_app()
    from landing.app import app
    return app


app = _crear_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
