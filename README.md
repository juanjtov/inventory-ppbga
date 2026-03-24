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

1. Crear proyecto en [Supabase](https://supabase.com)
2. Ejecutar `supabase/migrations/001_initial_schema.sql` en el SQL Editor
3. Habilitar Realtime en la tabla `products`
4. Crear el primer usuario owner:
   - En Supabase Auth: crear usuario con email/password
   - En la tabla `users`: insertar fila con `auth_id` = ID del auth user, `role = 'owner'`
5. Anotar: URL, anon key, service role key

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

Los tests corren contra una instancia real de Supabase. Requieren el backend corriendo:

```bash
cd backend
# Asegurar que el server esta corriendo en otra terminal
pytest tests/ -v
```

Variables necesarias para tests:
- `TEST_OWNER_EMAIL` — email del owner de prueba
- `TEST_OWNER_PASSWORD` — password del owner de prueba

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
