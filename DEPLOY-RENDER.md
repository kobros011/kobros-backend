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
3. `uvicorn` en el puerto `PORT` que Render inyecta

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

Clerk distingue **Development** y **Production**. Son instancias distintas (keys y usuarios no se mezclan).

### 3.1 Render `*.onrender.com` y Production

**Clerk no permite usar `kobros-frontend.onrender.com` (ni ningún `*.onrender.com`) como dominio de una instancia Production.** Necesitas un **dominio propio** (DNS que controles) y configurarlo en Render + Clerk.

| Objetivo | Clerk | Dominio del front | Keys |
|----------|--------|-------------------|------|
| Demo / prueba en Render | **Development** | `https://…onrender.com/srv1/login` | `pk_test_` / `sk_test_` |
| App “real” con Production | **Production** | `https://app.tudominio.com/srv1/login` (custom en Render) | `pk_live_` / `sk_live_` |

El aviso *development keys* en consola es **esperado** mientras uses `pk_test_` en Render; no es un bug de Kobros.

### 3.2 Pasos si tienes dominio propio

1. **Render → Static Site (front)** → Settings → **Custom Domains** → añade p. ej. `app.tudominio.com` (CNAME al host `*.onrender.com` que indique Render).
2. **Render → Web Service (API)** → custom domain opcional p. ej. `api.tudominio.com` (recomendado para CORS y cookies).
3. **Clerk Dashboard** → selector **Production** → **Create production instance** → dominio **`tudominio.com`** o subdominio que Clerk acepte (sigue el asistente).
4. **Clerk → Domains:** añade los registros DNS que pida Clerk (CNAME `clerk.…` hacia `frontend-api.clerk.services` u otro target que muestre el panel).
5. Cuando Production esté verificado, copia **pk_live_**, **sk_live_** y **JWKS** de Production.
6. Actualiza Render:
   - Front build: `VITE_CLERK_PUBLISHABLE_KEY`, `VITE_URL_API=https://api.tudominio.com`
   - API: `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `CORS_ORIGINS=https://app.tudominio.com`
7. En Clerk **Paths** (Production): Home / Sign-in → `https://app.tudominio.com/srv1/login` y redirect URLs `https://app.tudominio.com/srv1/*`.
8. Rebuild front + redeploy API. Vuelve a crear/vincular usuarios en **Production** (seed o `sync_users_to_clerk.py`).

Guía Clerk: [Deploy to production](https://clerk.com/docs/deployments/overview). Dominios en Render: [Custom domains](https://render.com/docs/custom-domains).

### 3.3 Configuración común (Development o Production)

1. [dashboard.clerk.com](https://dashboard.clerk.com) → instancia activa (Development **o** Production).
2. **API keys:** secret en backend; publishable en build del front (misma instancia).
3. **JWKS:** `CLERK_JWKS_URL` = URL que muestra Clerk para **esa** instancia (Development y Production tienen JWKS distintos).
4. **User & authentication:** username requerido; email opcional; password mín. 8; modo **Restricted**.
5. Username en Clerk: permitir `.` `_` `-` si usas `admin.carlos` en Kobros (`admin_carlos` en login si Clerk no permite punto).

Tras cambiar keys de Clerk, **rebuild** del Static Site y **redeploy** del backend.

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
| `VITE_CLERK_PUBLISHABLE_KEY` | **`pk_live_...`** en producción (no `pk_test_`) |
| `VITE_URL_API` | `https://kobros-backend.onrender.com` (sin barra final) |

Referencia: `kobros-frontend/.env.clerk.example`.

### Rutas SPA

Si al recargar rutas profundas ves 404, en Render Static Site añade una **Rewrite**:

1. Source: `/*`
2. Destination: `/index.html`
3. Action: Rewrite

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
| Perfil no carga tras login | Usuario en Clerk sin fila en Kobros o `clerk_user_id` vacío | Redeploy backend (seed) o `sync_users_to_clerk.py`; tras deploy, el primer `/auth/me` puede auto-vincular por username Clerk |
| Token inválido en `/auth/me` | `CLERK_JWKS_URL` / front con otro proyecto Clerk | Misma instancia Clerk en front y `CLERK_JWKS_URL` del backend |
| Aviso *development keys* en consola | Front con `pk_test_` en Render | Normal en demo; para `pk_live_` hace falta dominio propio + Clerk Production |
| Clerk rechaza `onrender.com` en Production | Política de Clerk | Usar instancia **Development** en Render **o** custom domain + Production |

---

## 9. Local vs Render

| | Local (`docker compose`) | Render |
|--|--------------------------|--------|
| DB | Contenedor `db` | Postgres managed |
| API | `:8000`, reload | Docker + `PORT` |
| Front | Vite `:5050` | Static `dist` |
| Env | `.env` / `.env.local` | Dashboard Render |

No subas `.env` al repositorio; solo `.env.clerk.example` como plantilla.
