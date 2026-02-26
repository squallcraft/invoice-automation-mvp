# Pasar a producción los últimos cambios

Tu servidor y Mercado Libre ya están configurados. Solo hay que **actualizar el código** en el servidor y volver a levantar la app.

---

## Opción A – El código está en GitHub (recomendado)

**1. Conectarte al servidor**

```bash
ssh root@TU_IP
```

(Reemplaza **TU_IP** por la IP de tu Droplet.)

**2. Ir al proyecto y traer los últimos cambios**

```bash
cd /opt/invoice-automation-mvp
git pull origin main
```

(Si tu rama se llama `master`, usa `git pull origin master`.)

**3. Reconstruir y levantar de nuevo**

```bash
docker compose build --no-cache
docker compose up -d
```

Si el **build del frontend** falla en `npm install` (exit code 1), el Dockerfile ya incluye `--legacy-peer-deps` y más memoria. Asegúrate de tener `git pull` reciente y vuelve a ejecutar `docker compose build --no-cache frontend`. Si sigue fallando, en el servidor prueba: `docker compose build --no-cache frontend 2>&1` y revisa el mensaje de error de npm.

**4. Si ves "password authentication failed for user postgres"**

El volumen de Postgres se creó con otra contraseña. Hay que recrear la base (ver sección *Crear una base de datos nueva* más abajo): `docker compose down` → borrar el volumen `invoice-automation-mvp_pgdata` → `docker compose up -d` → luego migraciones y admin.

**5. Si hubo cambios en la base de datos (migraciones)**

```bash
docker compose exec backend flask db upgrade
```

**6. Listo**

Abre en el navegador **https://app.TU_DOMINIO**. Si no ves los cambios, haz **recarga forzada** (Ctrl+Shift+R o Cmd+Shift+R) para que cargue el frontend nuevo.

**7. Si ves 422 en la consola al guardar Falabella o conectar Mercado Libre**

El backend puede devolver 422 cuando la **clave JWT es demasiado corta** (menos de 32 caracteres). En el servidor, edita `backend/.env` y asegúrate de que **SECRET_KEY** y **JWT_SECRET_KEY** tengan **al menos 32 caracteres**. Puedes generar una nueva clave con:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Pega el resultado en `JWT_SECRET_KEY=` (y si quieres, otra distinta en `SECRET_KEY=`). Luego reinicia el backend:

```bash
docker compose up -d backend
```

Los usuarios tendrán que **volver a iniciar sesión** después de cambiar la clave JWT.

---

## "password authentication failed for user postgres" (por qué pasa y cómo evitarlo)

**Qué está pasando:** El backend intenta conectar a Postgres con una contraseña, y la base tiene otra. Suele ser por una de estas dos cosas:

1. **`backend/.env` tiene `DATABASE_URL` con otra contraseña o con `localhost`.** El backend carga primero `backend/.env`; si ahí hay `DATABASE_URL`, puede usarla. En el servidor **no pongas `DATABASE_URL` en `backend/.env`** (o pon exactamente `DATABASE_URL=postgresql://postgres:postgres@db:5432/invoice_automation`). El `docker-compose.yml` ya define esa URL para que coincida con el contenedor `db`.
2. **El volumen de Postgres se creó con otra contraseña.** La contraseña de Postgres se fija **solo la primera vez** que se crea el volumen. Si en el pasado el `db` usó otra contraseña, ese volumen sigue esperando la antigua; el backend ahora usa `postgres:postgres` del compose y no coinciden. La solución es borrar el volumen una vez y dejar que se cree de nuevo con `postgres:postgres`.

**Pasos para que no vuelva a pasar:**

1. En el servidor, abre `backend/.env` y **borra la línea `DATABASE_URL=...`** si existe (o cámbiala a `DATABASE_URL=postgresql://postgres:postgres@db:5432/invoice_automation`).
2. Asegúrate de que en `docker-compose.yml` el servicio `backend` tenga en `environment:` la línea:  
   `DATABASE_URL: postgresql://postgres:postgres@db:5432/invoice_automation`  
   (no la quites al editar el compose).
3. Sigue la sección *Crear una base de datos nueva* una vez para recrear el volumen con la contraseña correcta.

---

## Crear una base de datos nueva (empezar de 0)

Si quieres **borrar toda la data** y tener una base limpia (por ejemplo después de actualizar el front), o si ves **"password authentication failed for user postgres"** aunque `DATABASE_URL` y `POSTGRES_PASSWORD` sean correctos (el volumen se creó en su día con otra contraseña):

```bash
cd /opt/invoice-automation-mvp
docker compose down
docker volume rm invoice-automation-mvp_pgdata
docker compose up -d
docker compose exec backend flask db upgrade
```

- **`docker compose down`**: para los contenedores.
- **`docker volume rm invoice-automation-mvp_pgdata`**: borra el volumen de PostgreSQL (toda la data).
- **`docker compose up -d`**: levanta de nuevo db, backend y frontend; Postgres se crea vacío con usuario `postgres` y contraseña `postgres`.
- **`flask db upgrade`**: crea todas las tablas desde cero.

Después crea un admin (o regístrate de nuevo):

```bash
docker compose exec backend python scripts/create_admin.py
```

### Si ya hiciste lo anterior y sigue "password authentication failed"

Puede que el **nombre del volumen** no sea `invoice-automation-mvp_pgdata` (Compose usa el nombre de la carpeta del proyecto). Primero revisa qué volumen está usando realmente el contenedor `db` y compáralo con el que piensas borrar.

**1. Con los contenedores levantados**, ver qué volumen usa el servicio `db`:

```bash
cd /opt/invoice-automation-mvp
docker compose ps -q db | xargs docker inspect --format '{{range .Mounts}}{{.Name}}{{end}}'
```

O, si prefieres ver nombre del contenedor y sus volúmenes:

```bash
docker inspect $(docker compose ps -q db) --format '{{.Name}}: {{range .Mounts}}{{.Name}} {{end}}'
```

Anota el nombre del volumen que salga (ej. `invoice-automation-mvp_pgdata` o `invoice_automation_mvp_pgdata`).

**2. Comparar**: si ese nombre **no** es `invoice-automation-mvp_pgdata`, entonces al borrar `invoice-automation-mvp_pgdata` no estabas borrando el volumen que usa la base; por eso la contraseña seguía fallando.

**3. Bajar, borrar ese volumen exacto y volver a crear todo:**

```bash
docker compose down
docker volume rm NOMBRE_QUE_VISTE_EN_EL_PASO_1
docker compose up -d
docker compose exec backend flask db upgrade
docker compose exec backend python scripts/create_admin.py
```

Para que el nombre del proyecto (y del volumen) sea siempre el mismo, en la raíz del proyecto puedes crear o editar `.env` y poner:

```
COMPOSE_PROJECT_NAME=invoice-automation-mvp
```

Así la próxima vez el volumen se llamará `invoice-automation-mvp_pgdata` y los pasos de esta doc coincidirán.

---

## Crear usuario admin en producción

En el servidor, desde la carpeta del proyecto:

```bash
docker compose exec backend python scripts/create_admin.py
```

Eso crea (o actualiza) el admin con email y contraseña por defecto del script. Para usar otro email/contraseña:

```bash
docker compose exec -e ADMIN_EMAIL=tu@email.com -e ADMIN_PASSWORD=tupassword backend python scripts/create_admin.py
```

---

## Opción B – El código no está en GitHub (subes desde tu Mac)

**1. Desde tu Mac**, empaqueta solo lo que cambió (o todo el proyecto) y súbelo al servidor. Ejemplo con `rsync` (cambia **TU_IP** y la ruta si es distinta):

```bash
cd /ruta/donde/está/invoice-automation-mvp
rsync -avz --exclude 'node_modules' --exclude '__pycache__' --exclude '.git' --exclude 'backend/.env' ./ root@TU_IP:/opt/invoice-automation-mvp/
```

- **No** sobrescribas `backend/.env` en el servidor (por eso está en `--exclude`).  
- Si no tienes `rsync`, puedes usar **scp** para copiar carpetas (por ejemplo `frontend/`, `backend/app/`, etc.).

**2. En el servidor**, reconstruir y levantar:

```bash
ssh root@TU_IP
cd /opt/invoice-automation-mvp
docker compose build --no-cache
docker compose up -d
docker compose exec backend flask db upgrade
```

**3. Probar** en **https://app.TU_DOMINIO** (recarga forzada si hace falta).

---

## Resumen (3 comandos en el servidor)

Si ya haces `git pull` desde el repo:

```bash
cd /opt/invoice-automation-mvp
git pull origin main
docker compose build --no-cache && docker compose up -d
docker compose exec backend flask db upgrade
```

Con eso queda en producción lo último que trabajaste (menú Ventas/Configuración, selector y botón Procesar, pantalla Integraciones con ML, Falabella y Haulmer).
