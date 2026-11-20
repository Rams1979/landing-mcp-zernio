# Landing + MCP + Zernio · Vivero Ryokuen (demo)

Taller "Marketing y Ventas con IA". Cifras y datos **ficticios**.

```
Landing (captura leads) → MCP (los expone) → Claude (analiza y escribe) → Zernio (publica) → más tráfico a la landing
```

## Qué hay

| Carpeta | Servicio Railway | Descripción |
|---|---|---|
| `landing/` | `landing` | FastAPI + Jinja. Una oferta, precio ancla, cupos reales por día, fecha límite y formulario que guarda cada lead. |
| `mcp_server/` | `mcp` | FastMCP (solo lectura) en `/mcp`. Herramientas: `estado_campana`, `cupos_por_dia`, `listar_leads`, `resumen_campana`. |
| `common/` | (compartido) | Configuración de la campaña, modelos y lógica de cupos. |
| `scripts/seed.py` | — | Carga leads ficticios. |

Los dos servicios usan la **misma base Postgres** y el mismo código del repo; solo cambia el comando de arranque.

## Despliegue en Railway (todo desde GitHub)

El repo trae `main.py` y `railway.json`: no hace falta configurar comandos en el panel.
Un mismo código, dos servicios; la variable `SERVICE` decide cuál arranca.

1. Proyecto nuevo → **Deploy from GitHub repo** → este repo. Será el servicio `landing`.
2. Agregar **Postgres** (`+ New → Database → PostgreSQL`).
3. Servicio `landing` → Variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `WHATSAPP_NEGOCIO` = número de prueba de 8 dígitos (opcional)
   - Settings → Networking → **Generate domain**.
4. `+ New → GitHub Repo` (el mismo repo) → servicio `mcp`. Variables:
   - `SERVICE` = `mcp`
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `MCP_TOKEN` = valor aleatorio largo (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - Generate domain.
5. (Opcional) Cargar datos ficticios: `python -m scripts.seed` desde la shell del servicio `landing`.

Ninguna clave va en el código: todo es variable de entorno (`.env` está en `.gitignore`).

## Conectar el MCP a Claude

URL del conector personalizado: `https://<dominio-mcp>.up.railway.app/<MCP_TOKEN>/mcp`

Claude no permite cabeceras propias en conectores personalizados y trata cualquier 401 como "usa OAuth".
Por eso el secreto va **en la ruta de la URL**; cualquier petición sin él recibe 404.
Clientes programáticos también pueden usar `Authorization: Bearer <MCP_TOKEN>` o `?key=<MCP_TOKEN>`.
El token queda en los logs de acceso y en la URL: aceptable para la demo; para producción conviene OAuth y rotarlo.

## Desarrollo local

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # SQLite por defecto; no subir .env
python -m pytest -q           # SQLite
TEST_DATABASE_URL=postgresql://user:pass@host/db python -m pytest -q   # incluye prueba de concurrencia
python -m uvicorn landing.app:app --reload
SERVICE=mcp MCP_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(32))") python main.py
```

## Seguridad

- Cupos protegidos con bloqueo de fila (`SELECT … FOR UPDATE`): no se sobrevende un día aunque lleguen reservas simultáneas (probado con 20 hilos en Postgres).
- Formulario: validación, campo honeypot, límite de 6 envíos por IP cada 10 min (en memoria, por instancia), cabeceras de seguridad.
- MCP: solo lectura, token comparado en tiempo constante, WhatsApp enmascarado y nombre abreviado en `listar_leads`. No arranca sin `MCP_TOKEN` de al menos 24 caracteres.
- Publicar en Zernio solo en cuenta de prueba y solo con aprobación humana.
