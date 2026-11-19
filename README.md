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

1. Proyecto nuevo → **Deploy from GitHub repo** → este repo. Se crea el servicio `landing`.
2. Agregar **Postgres** (`+ New → Database → PostgreSQL`).
3. Servicio `landing` → Settings → *Config as code* → ruta `railway.landing.json`. Variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `WHATSAPP_NEGOCIO` = número de prueba de 8 dígitos (opcional)
   - Settings → Networking → **Generate domain**.
4. `+ New → GitHub Repo` (el mismo repo) → servicio `mcp`. Config as code: `railway.mcp.json`. Variables:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
   - `MCP_TOKEN` = valor aleatorio largo (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
   - Generate domain.
5. (Opcional) Cargar datos ficticios: en el servicio `landing`, `railway run python -m scripts.seed` o desde la shell del servicio.

Ninguna clave va en el código: todo es variable de entorno (`.env` está en `.gitignore`).

## Conectar el MCP a Claude

URL del conector personalizado: `https://<dominio-mcp>.up.railway.app/mcp`

El servidor acepta el token como `Authorization: Bearer <MCP_TOKEN>` o como `?key=<MCP_TOKEN>`.
Si el formulario del conector en Claude no permite cabeceras, use la URL con `?key=`.
Ese token queda en la URL: es aceptable para la demo; para producción conviene OAuth y rotar el token.

## Desarrollo local

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # SQLite por defecto; no subir .env
python -m pytest -q           # SQLite
TEST_DATABASE_URL=postgresql://user:pass@host/db python -m pytest -q   # incluye prueba de concurrencia
python -m uvicorn landing.app:app --reload
MCP_TOKEN=$(python -c "import secrets;print(secrets.token_urlsafe(32))") python -m mcp_server
```

## Seguridad

- Cupos protegidos con bloqueo de fila (`SELECT … FOR UPDATE`): no se sobrevende un día aunque lleguen reservas simultáneas (probado con 20 hilos en Postgres).
- Formulario: validación, campo honeypot, límite de 6 envíos por IP cada 10 min (en memoria, por instancia), cabeceras de seguridad.
- MCP: solo lectura, token comparado en tiempo constante, WhatsApp enmascarado y nombre abreviado en `listar_leads`. No arranca sin `MCP_TOKEN` de al menos 24 caracteres.
- Publicar en Zernio solo en cuenta de prueba y solo con aprobación humana.
