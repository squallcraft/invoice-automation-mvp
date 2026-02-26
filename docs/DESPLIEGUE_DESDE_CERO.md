# Desplegar la app desde cero en un Droplet (sin errores)

Esta guía sirve para **borrar la app actual del Droplet** (si la tienes) y **subir de nuevo todo desde cero**, con la configuración correcta para que no vuelvan los errores de base de datos ni de JWT.

---

## Resumen rápido

1. En el Droplet: borrar la app antigua (contenedores, volumen, carpeta).
2. Clonar el repo de nuevo.
3. Crear `backend/.env` **sin** `DATABASE_URL` (el `docker-compose` la define).
4. Poner claves largas (≥32 caracteres) para `SECRET_KEY`, `JWT_SECRET_KEY` y `ENCRYPTION_KEY`.
5. Levantar con Docker, migraciones y crear el usuario admin.
6. Comprobar Nginx (o configurarlo si es un servidor nuevo).

---

## Parte 1 – Borrar la app antigua del Droplet (opcional)

Solo si ya tienes la app en el servidor y quieres empezar de cero.

1. Conéctate por SSH:

   ```bash
   ssh root@TU_IP_DROPLET
   ```

2. Entra en la carpeta del proyecto y para todo:

   ```bash
   cd /opt/invoice-automation-mvp
   docker compose down
   ```

3. Borra el volumen de Postgres (así la base se creará de nuevo con la contraseña correcta):

   ```bash
   docker volume rm invoice-automation-mvp_pgdata
   ```

   Si dice que el volumen no existe, sigue. Si el nombre es otro (p. ej. con guión bajo), anótalo y bórralo:

   ```bash
   docker volume ls | grep pgdata
   ```

4. (Opcional) Borrar la carpeta del proyecto para clonar de nuevo:

   ```bash
   cd /opt
   rm -rf invoice-automation-mvp
   ```

   Si prefieres no borrar la carpeta, en el paso 2 harás `git pull` en lugar de clonar.

---

## Parte 2 – Tener el código en el servidor

**Si borraste la carpeta** (`rm -rf invoice-automation-mvp`):

```bash
cd /opt
git clone https://github.com/squallcraft/invoice-automation-mvp.git
cd invoice-automation-mvp
```

(Sustituye la URL por tu repo si es otro.)

**Si no borraste la carpeta**, solo actualiza:

```bash
cd /opt/invoice-automation-mvp
git pull origin main
```

---

## Parte 3 – Crear `backend/.env` (correcto, sin DATABASE_URL)

En el servidor:

```bash
cd /opt/invoice-automation-mvp
cp backend/.env.example backend/.env
nano backend/.env
```

**Importante:** No añadas ninguna línea `DATABASE_URL` en este archivo. El `docker-compose.yml` ya define la URL de la base (postgres/postgres en el contenedor `db`). Si pones `DATABASE_URL` en `.env` con un error (espacio, otra contraseña), volverán los errores de “password authentication failed”.

Completa el `.env` así (cambia los valores por los tuyos):

```env
FLASK_APP=app.app
FLASK_ENV=production
SECRET_KEY=peg_aquí_una_clave_de_al_menos_32_caracteres
JWT_SECRET_KEY=peg_aquí_otra_clave_de_al_menos_32_caracteres
ENCRYPTION_KEY=peg_aquí_clave_fernet_44_caracteres
HAULMER_API_BASE=https://docsapi-openfactura.haulmer.com
FALABELLA_API_BASE=https://api.falabella.com/seller
ML_CLIENT_ID=tu_app_id_mercado_libre
ML_CLIENT_SECRET=tu_secret_mercado_libre
ML_REDIRECT_URI=https://app.trackinginvoice.cl/api/mercado-libre/callback
# Chile = auth.mercadolibre.cl ; Argentina = auth.mercadolibre.com.ar
ML_AUTH_BASE=https://auth.mercadolibre.cl
FRONTEND_URL=https://app.trackinginvoice.cl
```

- Sustituye `app.trackinginvoice.cl` por tu dominio si es otro.
- `SECRET_KEY` y `JWT_SECRET_KEY`: mínimo 32 caracteres. Puedes generar dos claves con:

  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

  Ejecuta dos veces y usa una para `SECRET_KEY` y otra para `JWT_SECRET_KEY`.

- `ENCRYPTION_KEY`: clave Fernet de 44 caracteres. Generar con:

  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

Guarda el archivo (Ctrl+O, Enter) y cierra nano (Ctrl+X).

---

## Parte 4 – Levantar la app con Docker

Desde la carpeta del proyecto:

```bash
cd /opt/invoice-automation-mvp
docker compose up -d --build
```

Espera a que termine el build y que los contenedores estén en “Up”. Comprueba:

```bash
docker compose ps
```

Debes ver `db`, `backend` y `frontend` en ejecución.

---

## Parte 5 – Migraciones y usuario admin

```bash
docker compose exec backend flask db upgrade
docker compose exec backend python scripts/create_admin.py
```

Sigue las indicaciones para crear el usuario admin (email y contraseña). Este será el usuario con el que iniciarás sesión.

---

## Parte 6 – Nginx (si ya lo tenías configurado)

Si en este Droplet ya tenías Nginx apuntando a la app:

- El sitio debe hacer `proxy_pass` a `http://127.0.0.1:5000` para `/api/` y a `http://127.0.0.1:3000` para `/`.
- No hace falta cambiar nada más; solo asegúrate de que Nginx esté activo:

  ```bash
  nginx -t && systemctl reload nginx
  ```

Si es un servidor nuevo y aún no tienes Nginx, sigue la **Parte 4** de `DESPLIEGUE_PASO_A_PASO.md` (crear sitio en Nginx, Certbot, etc.).

---

## Parte 7 – Probar

1. Abre en el navegador: `https://app.tu-dominio.com` (o el dominio que uses).
2. Inicia sesión con el usuario admin que creaste.
3. Ve a Configuración → Integraciones y prueba Mercado Libre y Falabella si lo necesitas.

Si algo falla, revisa los logs:

```bash
docker compose logs backend --tail=50
```

---

## Si "password authentication failed" vuelve a aparecer (arreglo en un solo paso)

En el servidor, desde la carpeta del proyecto, ejecuta **una sola vez**:

```bash
cd /opt/invoice-automation-mvp
bash scripts/fix-db-and-backend-once.sh
```

Ese script: quita `DATABASE_URL` del `.env` si existe, comprueba el compose, baja todo, borra el volumen de Postgres, levanta de nuevo, ejecuta migraciones y `create_admin`, y verifica que backend y db usen la misma contraseña. Después de eso, **no vuelvas a poner `DATABASE_URL` en `backend/.env`** ni borres la línea `DATABASE_URL` del `docker-compose.yml` al editar; así no se desincroniza de nuevo.

---

## Checklist final (evitar errores)

- [ ] No hay línea `DATABASE_URL` en `backend/.env`.
- [ ] `SECRET_KEY` y `JWT_SECRET_KEY` tienen al menos 32 caracteres cada una.
- [ ] `ML_REDIRECT_URI` usa **https** y termina en `/api/mercado-libre/callback`.
- [ ] Después de `docker compose up -d`, ejecutaste `flask db upgrade` y `create_admin.py`.
- [ ] Nginx hace proxy de `/api/` al puerto 5000 y `/` al 3000.

---

## Por qué vuelve "password authentication failed" cada vez que haces compose (o migración)

**Qué pasa cada vez que ejecutas `docker compose up -d` o `docker compose up -d backend`:**

1. Docker Compose **crea o recrea** el contenedor del backend.
2. El contenedor **no guarda** la configuración anterior: cada vez que nace, lee su entorno desde:
   - **`backend/.env`** (archivo que tú editas en el servidor)
   - **`docker-compose.yml`** → bloque `environment:` del servicio `backend` (lo que está en el **archivo** en el servidor en ese momento)

3. Si en el servidor **no** está la línea `DATABASE_URL` en el `docker-compose.yml` (porque se borró al editar a mano, porque hay un `docker-compose.override.yml` que la quita, o porque el `git pull` no actualizó ese archivo), el backend **solo** tendrá la `DATABASE_URL` que venga del `.env`. Si ahí hay un error (espacio, otra contraseña, `localhost`), la conexión falla.

**Por eso “se arregla y luego vuelve a fallar”:** no es que la base cambie; es que **cada vez que el contenedor backend se recrea**, vuelve a leer los archivos. Si en el servidor esos archivos están mal (compose sin `DATABASE_URL` o `.env` con una mala), el “arreglo” que hiciste (por ejemplo borrar `DATABASE_URL` del `.env`) se mantiene, pero si el compose en el servidor **no** tiene `DATABASE_URL`, el backend sigue sin recibir la URL correcta. O al revés: si alguien vuelve a poner `DATABASE_URL` en el `.env` con un typo, la próxima vez que hagas `compose up` el backend usará esa URL errónea otra vez.

**Sobre las migraciones:** `docker compose exec backend flask db upgrade` **no** recrea el contenedor; solo ejecuta un comando dentro del que ya está corriendo. El fallo no “vuelve” por la migración en sí, sino si **después** haces un `docker compose up -d` (o rebuild) y se recrea el backend con la configuración incorrecta de nuevo.

---

## Cómo evitarlo para siempre (en el servidor)

La URL de la base **solo** debe venir del `docker-compose.yml`, y el `backend/.env` **nunca** debe definir `DATABASE_URL` cuando usas Docker.

**Verificación en el servidor (ejecutar después de cada `docker compose up -d backend`):**

```bash
# 1) El .env NO debe definir DATABASE_URL (no debe imprimir nada):
grep DATABASE_URL /opt/invoice-automation-mvp/backend/.env && echo ">>> BORRA ESA LÍNEA de backend/.env" || echo "OK: .env no tiene DATABASE_URL"

# 2) El compose SÍ debe definir DATABASE_URL (debe aparecer la línea):
grep "DATABASE_URL:" /opt/invoice-automation-mvp/docker-compose.yml || echo ">>> AÑADE DATABASE_URL en environment: del backend en docker-compose.yml"

# 3) Lo que ve el contenedor (debe ser postgres:postgres@db:5432):
docker compose exec backend env | grep DATABASE_URL
```

Si (1) imprime algo → borra esa línea del `.env`. Si (2) no imprime nada → añade en `docker-compose.yml`, en el servicio `backend`, dentro de `environment:`:

```yaml
DATABASE_URL: postgresql://postgres:postgres@db:5432/invoice_automation
```

Luego: `docker compose up -d backend --force-recreate`. Así deja de volver a aparecer.
