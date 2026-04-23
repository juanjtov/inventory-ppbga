# Premier Padel BGA — Sistema de Inventario

Sistema de inventario web desktop-first para la cafeteria de Premier Padel BGA (Bucaramanga, Colombia). Gestiona ventas, stock en tiempo real, cuentas abiertas (fiado), corte de caja y reportes.

## Tech Stack

| Capa | Tecnologia | Host |
|------|-----------|------|
| Frontend | React 18 + Vite + Tailwind CSS 3 | Vercel |
| Backend | FastAPI (Python 3.11+) | Koyeb |
| Base de datos | PostgreSQL | Supabase |
| Auth | Supabase Auth | Supabase |
| Realtime | Supabase Realtime | Supabase |

## Estructura del Proyecto

```
inventorypp/
├── frontend/          # React + Vite + Tailwind
├── backend/           # FastAPI
│   ├── app/
│   │   ├── models/    # Pydantic schemas
│   │   ├── routers/   # API endpoints
│   │   └── services/  # Business logic
│   └── tests/         # Pytest test suite
├── supabase/
│   └── migrations/    # SQL schema
└── seed_data/         # CSV de inventario inicial
```

## Setup

### 1. Base de datos (Supabase)

Esta seccion describe como crear un nuevo entorno desde cero. Para el flujo de
trabajo dev/prod ya separado, ver la seccion [Entornos Dev / Prod](#entornos-dev--prod) abajo.

1. Crear proyecto en [Supabase](https://supabase.com) (recomendado: nombrarlo `inventorypp-dev` para uso local)
2. Aplicar las migraciones con el script:
   ```bash
   TARGET_DATABASE_URL='postgresql://postgres:pwd@db.<ref>.supabase.co:5432/postgres?sslmode=require' \
     ./scripts/apply_migrations.sh
   ```
   Esto ejecuta todo `supabase/migrations/*.sql` en orden lexico.
3. Habilitar Realtime en la tabla `products` (la migracion 001 ya lo hace via `ALTER PUBLICATION`)
4. Crear el primer usuario owner con el script:
   ```bash
   DEV_SUPABASE_URL='https://<ref>.supabase.co' \
   DEV_SUPABASE_SECRET_KEY='sb_secret_...' \
   DEV_DATABASE_URL='postgresql://postgres:pwd@db.<ref>.supabase.co:5432/postgres?sslmode=require' \
     ./scripts/create_dev_owner.sh
   ```
5. Anotar: URL, publishable key, secret key, project ref

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Crear `backend/.env`:
```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_SECRET_KEY=sb_secret_...
CORS_ORIGINS=http://localhost:5173
```

Ejecutar:
```bash
uvicorn app.main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
```

Crear `frontend/.env`:
```env
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Ejecutar:
```bash
npm run dev
```

### 4. Tests

Los tests corren contra el proyecto Supabase de **dev** (`inventorypp-dev`),
nunca contra prod. El backend debe estar corriendo localmente:

```bash
cd backend
# Asegurar que el server esta corriendo en otra terminal
pytest tests/ -v
```

Variables necesarias para tests:
- `TEST_OWNER_EMAIL` — email del owner de prueba (creado via `scripts/create_dev_owner.sh`)
- `TEST_OWNER_PASSWORD` — password del owner de prueba

## Entornos Dev / Prod

El proyecto usa **dos proyectos Supabase separados**:

| Entorno | Donde | Credenciales |
|---------|-------|--------------|
| **Dev** (`inventorypp-dev`) | Local (laptop) | `backend/.env`, `frontend/.env` |
| **Prod** (Premier Padel BGA real) | Koyeb + Vercel | Variables en los dashboards de Koyeb y Vercel |

**Reglas:**

- Local siempre apunta a dev. Tus archivos `backend/.env` y `frontend/.env`
  contienen URL y keys del proyecto `inventorypp-dev`.
- Las credenciales de prod **nunca** estan en el repo, ni en `.env`, ni en
  ningun archivo del proyecto. Viven solo en los dashboards de Koyeb y Vercel.
- El backend imprime un log al inicio con el project ref de Supabase
  (`Supabase project: <ref>`) para que cualquier configuracion errada sea
  inmediatamente visible.

**Operaciones de base de datos** estan en `scripts/` — backup, restore,
aplicar migraciones, crear owner. Ver [`scripts/README.md`](scripts/README.md)
para el detalle completo, incluyendo como guardar la URL de prod en el
Keychain de macOS de forma segura.

> **Aviso de seguridad:** las variables `VITE_*` se compilan dentro del
> bundle de frontend en tiempo de build y son publicamente visibles. Solo
> usar publishable keys ahi, jamas el secret key.

## Deployment

### Frontend (Vercel)
- Root directory: `frontend/`
- Build: `npm run build`
- Output: `dist`
- Env vars: `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_API_BASE_URL`

### Backend (Koyeb)
- Root directory: `backend/`
- Builder: Dockerfile
- Port: 8000
- Health check: `/health`
- Env vars: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `CORS_ORIGINS`

## Importar Inventario Inicial

1. Login como owner
2. Ir a Catalogo
3. Click "Importar CSV"
4. Subir `seed_data/Inventario_Premier_Mar_23.csv`

## Funcionalidades

- **POS** — Punto de venta con busqueda, filtros y 4 metodos de pago
- **Inventario** — Stock en tiempo real con alertas de bajo stock
- **Cuentas Abiertas** — Gestion de fiados con envejecimiento por dias
- **Corte de Caja** — Cierre diario con diferencia de efectivo
- **Reportes** — Ventas, valoracion de inventario, reconciliacion
- **Catalogo** — CRUD de productos con importacion CSV
- **Usuarios** — Gestion de roles (owner/admin/worker)
- **Auditoria** — Log de cambios de precios y modificaciones
- **Atajos de teclado** — Enter para confirmar venta en POS
- **Recibo de venta** — Vista previa imprimible
- **Exportar CSV** — En reportes e historial de ventas
