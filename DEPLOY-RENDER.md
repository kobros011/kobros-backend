# Deploy Kobros en Render

Guía para publicar **backend** (Web Service + Docker), **PostgreSQL** y **frontend** (Static Site) en [Render](https://render.com).

Repositorios:

| Componente | GitHub |
|------------|--------|
| API | `https://github.com/kobros011/kobros-backend` |
| Frontend | `https://github.com/kobros011/kobros-frontend` |

---

## 1. PostgreSQL

1. Render Dashboard → **New** → **PostgreSQL**.
2. Nombre sugerido: `kobros-db`.
3. Región: la misma que usarás para API y front.
4. Tras crear, copia la **Internal Database URL** (para la API en Render) y, si hace falta, la **External** (solo para herramientas locales).

### Formato de `DATABASE_URL` para la API

La app usa **asyncpg**. Convierte la URL de Render:

```text
# Render entrega:
postgresql://USER:PASS@HOST/DB

# En variables de entorno del backend:
postgresql+asyncpg://USER:PASS@HOST/DB
```

Alembic sustituye `+asyncpg` por `+psycopg2` automáticamente al migrar.

---

## 2. Backend (Web Service)

1. **New** → **Web Service** → conectar repo `kobros-backend`.
2. **Branch:** `main`.
3. **Runtime:** Docker (usa el `Dockerfile` del repo).
4. **Instance type:** según carga (Free tier válido para pruebas).

### Comando de arranque (ya en Dockerfile)

Al iniciar el contenedor:

1. `alembic upgrade head`
2. `python scripts/ensure_dev_users.py` (crea `admin.carlos` y `admin.david` si no existen)
3. `uvicorn` en el puerto **`PORT`** que Render inyecta

No hace falta un Start Command extra si usas el Dockerfile tal cual.

### Variables de entorno (Environment)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DATABASE_URL` | Sí | `postgresql+asyncpg://...` (Internal URL de Postgres) |
| `CLERK_SECRET_KEY` | Sí | Secret key de Clerk |
| `CLERK_JWKS_URL` | Sí | JWKS del frontend API de Clerk |
| `CORS_ORIGINS` | Sí | URL del front en Render, ej. `https://kobros-frontend.onrender.com` |
| `DEV_SEED_CARLOS_PASSWORD` | Recomendado | Mín. 8 caracteres (bootstrap dev) |
| `DEV_SEED_DAVID_PASSWORD` | Recomendado | Mín. 8 caracteres (bootstrap dev) |
| `DEV_SEED_DISABLED` | No | `true` para omitir seed en prod sin devs |

Referencia completa Clerk y seed: `.env.clerk.example`.

### Health check (opcional)

- **Health Check Path:** `/docs` o un endpoint ligero si añades `/health`.

### URL pública

Anota la URL del servicio, ej. `https://kobros-api.onrender.com`. La usarás en el frontend como `VITE_URL_API`.

---

## 3. Clerk

1. [dashboard.clerk.com](https://dashboard.clerk.com) → instancia de la app.
2. **API keys:** `CLERK_SECRET_KEY`, publishable key para el front.
3. **JWKS:** `CLERK_JWKS_URL` = `https://<tu-clerk-host>/.well-known/jwks.json`.
4. **User & authentication:** username requerido; email opcional; password mín. 8; modo **Restricted** (sin registro público).
5. Si Clerk no permite `.` en username, el backend normaliza a `_` en Clerk (`admin.carlos` → `admin_carlos`).

Tras el primer deploy, revisa logs del backend: si el seed generó contraseñas temporales, cámbialas en Clerk o define `DEV_SEED_*_PASSWORD` antes del deploy.

---

## 4. Frontend (Static Site)

1. **New** → **Static Site** → repo `kobros-frontend`.
2. **Branch:** `main`.
3. **Build Command:** `npm install && npm run build`
4. **Publish Directory:** `dist`

### Variables de entorno (Build time)

Render las inyecta en el build de Vite:

| Variable | Ejemplo |
|----------|---------|
| `VITE_CLERK_PUBLISHABLE_KEY` | `pk_live_...` o `pk_test_...` |
| `VITE_URL_API` | `https://kobros-api.onrender.com` (sin barra final) |

Referencia: `kobros-frontend/.env.clerk.example`.

### Rutas SPA

Si al recargar rutas profundas ves 404, en Render Static Site añade una **Rewrite**:

- Source: `/*`
- Destination: `/index.html`
- Action: Rewrite

---

## 5. Orden recomendado

```mermaid
flowchart LR
  PG[(PostgreSQL)]
  API[Web Service API]
  CL[Clerk config]
  FE[Static Site Front]

  PG --> API
  CL --> API
  CL --> FE
  API --> FE
```

1. Crear Postgres y anotar URL.
2. Desplegar API con env vars + `CORS_ORIGINS` (puede ser URL provisional del front).
3. Configurar Clerk (JWKS + keys).
4. Desplegar front con `VITE_URL_API` apuntando a la API.
5. Actualizar `CORS_ORIGINS` en la API con la URL final del Static Site.
6. Probar login con `admin_carlos` / `admin_david` (Clerk) según contraseñas de seed.

---

## 6. Comprobaciones post-deploy

| Prueba | Cómo |
|--------|------|
| Migraciones | Logs API: `alembic upgrade head` sin error |
| Seed dev | Logs: `SKIP` o `CREADO admin.carlos` / `admin.david` |
| API | Abrir `https://<api>/docs` |
| CORS | Login desde el front; sin error de red en `/auth/me` |
| Clerk | Sign-in con usuario dev; JWT en requests |

---

## 7. Scripts útiles (local o one-off en Render Shell)

```bash
# Solo simular seed
python scripts/ensure_dev_users.py --dry-run

# Vincular usuarios Kobros existentes sin clerk_user_id
python scripts/sync_users_to_clerk.py
```

En Render: **Shell** del Web Service (plan de pago) o ejecutar localmente contra `DATABASE_URL` external.

---

## 8. Troubleshooting

| Síntoma | Causa habitual | Acción |
|---------|----------------|--------|
| 403 / CORS | Front no listado en `CORS_ORIGINS` | Añadir URL exacta del Static Site |
| DB connection | URL sin `+asyncpg` o URL external bloqueada | Internal URL + prefijo asyncpg |
| Identifier invalid (Clerk) | Punto no permitido en username | Login con `admin_carlos` o permitir `.` en Clerk |
| API no arranca | Puerto fijo | Dockerfile ya usa `${PORT:-8000}` |
| Front sin API | Build sin env | Rebuild con `VITE_URL_API` definida |

---

## 9. Local vs Render

| | Local (`docker compose`) | Render |
|--|--------------------------|--------|
| DB | Contenedor `db` | Postgres managed |
| API | `:8000`, reload | Docker + `PORT` |
| Front | Vite `:5050` | Static `dist` |
| Env | `.env` / `.env.local` | Dashboard Render |

No subas `.env` al repositorio; solo `.env.clerk.example` como plantilla.
