# Reiniciar base de datos desde cero y tarea cada 10 min

## Reiniciar la base de datos (borrar todo y empezar de cero)

**En el servidor (SSH al Droplet):**

```bash
cd /opt/invoice-automation-mvp
docker compose down
docker volume rm invoice-automation-mvp_pgdata
docker compose up -d
```

Espera ~15 segundos y luego:

```bash
docker compose exec backend flask db upgrade
docker compose exec backend python scripts/create_admin.py
```

Comprueba que `backend/.env` tenga:

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/invoice_automation
```

Si no, corrígelo y ejecuta `docker compose up -d backend`. Luego podrás entrar con **o.guzman@grupoenix.com** / **123456789**.

---

## Tarea cada 10 min (traer ventas de Falabella y Mercado Libre)

La app intenta ejecutar una tarea interna cada 10 minutos. Si usas varios workers (gunicorn -w 4), es mejor **no** depender del scheduler y usar **cron** en el servidor.

### Opción A: Cron en el servidor

1. Genera un secreto (ej. `openssl rand -hex 16`) y añádelo al `.env` del backend:
   ```env
   CRON_SECRET=tu_secreto_aqui
   ```

2. En el servidor, edita el crontab:
   ```bash
   crontab -e
   ```

3. Añade esta línea (cada 10 min, llamando al backend por el puerto interno):
   ```
   */10 * * * * curl -s -H "X-Cron-Secret: tu_secreto_aqui" http://127.0.0.1:5000/internal/sync-sales
   ```

4. Reinicia el backend para que cargue `CRON_SECRET`:
   ```bash
   docker compose restart backend
   ```

### Opción B: Scheduler dentro de la app

Si solo tienes **un** worker de gunicorn, el scheduler puede estar activo (se inicia al arrancar el backend). No hace falta configurar cron; cada 10 min se ejecutará la sincronización.

---

## Campos que verá el usuario (ventas)

- **Plataforma** (primera columna): Falabella | Mercado Libre | Manual  
- **ID venta**  
- **Fecha documento**  
- **Monto**, **Tipo doc** (Boleta/Factura)  
- **Estado**: Pendiente | Éxito | Error  
- **Documento cargado**: sí/no (si se subió correctamente a la plataforma)  
- **Fecha de carga** (cuando se subió el documento a Falabella/ML)

El endpoint `GET /dashboard/sales` devuelve además `platform`, `document_date`, `documento_cargado`, `document_uploaded_at` para armar la vista en el frontend.
