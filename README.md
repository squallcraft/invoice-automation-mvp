# Invoice Automation MVP

MVP para automatizar la emisión de boletas y facturas para vendedores e-commerce, integrando **Haulmer** (documentos tributarios) y **Falabella Seller** (ventas y subida de documentos).

## Stack

- **Backend:** Python, Flask, SQLAlchemy, PostgreSQL, Alembic, JWT, cryptography (Fernet)
- **Frontend:** React, React Router, Axios
- **APIs externas:** Haulmer (OpenFactura), Falabella Seller (endpoints genéricos; ajustar según documentación real)

## Estructura

```
invoice-automation-mvp/
├── backend/
│   ├── app/
│   │   ├── __init__.py      # Factory Flask, CORS, JWT, blueprints
│   │   ├── models.py        # User, Sale, Document
│   │   ├── crypto_utils.py  # Encriptación API keys
│   │   ├── routes/          # auth, config, auto, semi, dashboard
│   │   └── services/        # haulmer_client, falabella_client
│   ├── migrations/          # Alembic
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/      # Login, Register, Dashboard, Config, FileUpload
│   │   ├── context/         # AuthContext
│   │   └── api/             # client axios
│   └── package.json
├── docker-compose.yml
└── README.md
```

## Cómo correr en local

### Opción rápida (script)

Con PostgreSQL ya corriendo en `localhost:5432`:

```bash
./scripts/run-local.sh
```

Levanta backend (5000) y frontend (3000). Si Postgres no está instalado o no está activo:

**Instalar y arrancar Postgres con Homebrew (macOS):**

```bash
brew install postgresql@15
brew services start postgresql@15
# En Mac con Apple Silicon, añade el binario al PATH para esta sesión:
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
createdb invoice_automation
./scripts/run-local.sh
```

### 1. Base de datos

PostgreSQL en puerto 5432. Crear BD:

```bash
createdb invoice_automation
```

O con Docker solo para la BD (desde la raíz del proyecto):

```bash
docker compose up -d db
```

O un contenedor suelto:

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=invoice_automation -p 5432:5432 postgres:15-alpine
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Crear `.env` (copiar de `.env.example`):

- `DATABASE_URL=postgresql://usuario:password@localhost:5432/invoice_automation`
- `SECRET_KEY` y `JWT_SECRET_KEY`: valores aleatorios
- `ENCRYPTION_KEY`: generar con  
  `python scripts/generate_fernet_key.py`  
  (o desde la raíz: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)

Migraciones (desde el directorio `backend`, con `FLASK_APP=app.app`):

```bash
cd backend
export FLASK_APP=app.app
flask db upgrade
```

Arrancar la app:

```bash
cd backend
python app/app.py
# o: flask run --host=0.0.0.0 --port=5000
```

Backend disponible en `http://localhost:5000`. Health: `GET /health`.

### 3. Frontend

```bash
cd frontend
npm install
npm start
```

Abre `http://localhost:3000`. El frontend usa por defecto `http://localhost:5000`; si cambias el puerto del backend, configura `REACT_APP_API_URL` en `.env` del frontend.

## API (resumen)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /auth/register | Registro |
| POST | /auth/login | Login (devuelve JWT) |
| GET/PUT | /config/keys | Ver/guardar API keys y Falabella User ID (encriptadas) |
| POST | /auto/process | Flujo automático: procesar ventas (Falabella + Haulmer) |
| POST | /semi/upload | Subir Excel/CSV y obtener previsualización |
| POST | /semi/process-batch | Emitir en lote y resultado (ZIP opcional) |
| GET | /dashboard/sales | Listado de ventas (filtro por status) |
| POST | /dashboard/sales/:id/retry | Reintentar venta en error |
| **Falabella Seller Center** | | |
| GET | /falabella/orders | Órdenes (query: created_after, updated_after, status, limit, offset) |
| GET | /falabella/orders/:order_id/items | Ítems de una orden (OrderItemIds para etiquetas) |
| POST | /falabella/labels | Obtener etiquetas (body: order_item_ids o order_id; ?download=1 para PDF) |

Proteger con `Authorization: Bearer <token>` todas excepto register/login.

### Falabella: obtener etiquetas

1. En **Configuración** guarda tu **Falabella User ID** (email de Seller Center) y **API Key** (desde Manage Users / Mi cuenta).
2. **Órdenes:** `GET /falabella/orders?created_after=2025-01-01T00:00:00+00:00`
3. **Ítems de una orden:** `GET /falabella/orders/<OrderId>/items` → obtienes los `OrderItemId`.
4. **Etiquetas:** Los ítems deben estar empaquetados (SetStatusToReadyToShip). Luego:
   - `POST /falabella/labels` con `{"order_item_ids": [123, 456]}` o `{"order_id": 1127812574}`.
   - Añade `?download=1` para descargar el PDF directamente.

## Flujos

1. **Automático:** La app obtiene órdenes aprobadas de Falabella (polling o webhook), emite documento en Haulmer y puede subir el PDF a Falabella. Endpoint: `POST /auto/process`.
2. **Semi-automático:** El usuario sube Excel/CSV con columnas `id_venta`, `tipo_documento`, `monto`. Se valida, se previsualiza y al confirmar se emite en lote y se entrega ZIP (o enlace). Endpoints: `POST /semi/upload` y `POST /semi/process-batch`.

## Idempotencia y errores

- En la tabla `sales` hay constraint único `(user_id, id_venta)` para evitar duplicados.
- Ventas en estado Error se pueden reintentar con `POST /dashboard/sales/:id/retry` o enviando la misma venta en `POST /auto/process` con `"retry": true`.

## Docker (todo el stack)

En la raíz del proyecto:

```bash
# Generar ENCRYPTION_KEY y exportarla
export ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
docker compose up --build
```

- Backend: `http://localhost:5000`
- Frontend (nginx): `http://localhost:3000`
- PostgreSQL: puerto 5432 (solo red interna si no se expone).

Antes la primera vez, ejecutar migraciones dentro del contenedor backend:

```bash
docker compose exec backend flask db upgrade
```

## Tests (sugerencia)

- **Backend:** `pytest` en `backend/tests/` (fixtures con BD de prueba, mocks de Haulmer/Falabella).
- **Frontend:** `npm test` (Jest + React Testing Library) para componentes y flujos críticos.

## Mercado Libre (esbozo)

- **OAuth:** La app debe estar registrada en [Mercado Libre Dev Center](https://developers.mercadolibre.com.ar/devcenter) con una **Redirect URI HTTPS** (ej. `https://tu-dominio.com/mercado-libre/callback`). No hace falta tener la app en producción: puedes usar un túnel (ngrok) o un deploy staging con HTTPS. Ver [docs/MERCADO_LIBRE.md](docs/MERCADO_LIBRE.md).
- **Env:** `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`, opcional `ML_AUTH_BASE` (por país), `FRONTEND_URL`.
- **Rutas:** `GET /mercado-libre/auth` (inicia OAuth), `GET /mercado-libre/callback` (recibe code y guarda tokens), `GET /mercado-libre/orders`, `POST /mercado-libre/upload-invoice` (pack_id o order_id + PDF).

## Despliegue en producción

Si ya tienes dominio (ej. GoDaddy) y quieres montar la app en producción, sigue la guía **[docs/DEPLOY_PRODUCCION.md](docs/DEPLOY_PRODUCCION.md)**. Incluye: uso de GitHub, opciones de hosting (Railway, Render), variables de entorno y cómo apuntar tu dominio.

## Notas

- Las URLs y payloads de Haulmer y Falabella son orientativas; hay que ajustarlas a la documentación oficial de cada API.
- En producción usar HTTPS, secrets en variables de entorno o gestor de secretos, y no exponer `ENCRYPTION_KEY` ni las API keys en logs.
