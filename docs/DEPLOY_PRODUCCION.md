# Montar la app en producción

Resumen: **backend + base de datos + frontend** en un proveedor con HTTPS, y tu **dominio de GoDaddy** apuntando ahí.

---

## 1. ¿Hace falta GitHub?

**No es obligatorio**, pero **sí es muy recomendable**:

- La mayoría de plataformas (Railway, Render, Fly.io) se conectan a un **repositorio Git** y despliegan cada vez que haces push.
- Sin GitHub tendrías que subir el código a mano o usar su CLI cada vez.

**Qué hacer:** Crear un repositorio en GitHub, subir tu proyecto (`invoice-automation-mvp`) y conectar ese repo con la plataforma que elijas.

---

## 2. Qué necesitas tener

| Concepto | Dónde |
|----------|--------|
| **Código** | Repo en GitHub (recomendado) |
| **Dominio** | Ya lo tienes en GoDaddy |
| **Base de datos PostgreSQL** | Incluida en Railway/Render o servicio externo (Neon, Supabase) |
| **Backend (Flask)** | Se despliega en la misma plataforma |
| **Frontend (React)** | Build estático; mismo servicio o Vercel/Netlify |
| **Variables de entorno** | Las configuras en el panel de la plataforma (secretos) |
| **HTTPS** | Lo da la plataforma; luego apuntas el dominio desde GoDaddy |

---

## 3. Opciones de hosting (recomendadas)

### Opción A: Railway (muy sencillo)

- [railway.app](https://railway.app) – plan gratuito limitado, luego de pago.
- Puedes crear: **PostgreSQL** + **Backend** (desde Dockerfile o repo) + **Frontend** (build de React).
- Te dan una URL tipo `tu-app.up.railway.app` con HTTPS. Esa URL (o tu dominio) la usas como **Redirect URI** de Mercado Libre.
- Conectar el repo de GitHub y configurar variables de entorno. Railway detecta el `Dockerfile` o puedes usar Nixpacks.

### Opción B: Render

- [render.com](https://render.com) – plan gratuito para web services y Postgres (con límites).
- Creas: **PostgreSQL**, **Web Service** (backend), **Static Site** (frontend).
- Te dan `tu-app.onrender.com` con HTTPS. Igual que arriba, esa URL o tu dominio sirve para ML.

### Opción C: Un VPS (DigitalOcean, Linode, etc.)

- Tú instalas Docker y corres `docker-compose` o los servicios a mano. Más control, más trabajo. No es necesario para un MVP.

**Recomendación para empezar:** Railway o Render; ambos dan HTTPS y base de datos sin configurar servidores.

---

## 4. Pasos concretos (ejemplo con Railway)

1. **Subir código a GitHub**
   - Crea un repo (ej. `invoice-automation-mvp`).
   - En tu máquina: `git init`, `git add .`, `git commit -m "Initial"`, `git remote add origin ...`, `git push -u origin main`.

2. **Crear proyecto en Railway**
   - Entra a [railway.app](https://railway.app), inicia sesión con GitHub.
   - “New Project” → “Deploy from GitHub repo” → elige tu repo.

3. **Añadir PostgreSQL**
   - En el proyecto: “New” → “Database” → “PostgreSQL”. Railway te da una URL de conexión (ej. `DATABASE_URL`).

4. **Desplegar el backend**
   - “New” → “GitHub Repo” (el mismo) → selecciona el repo.
   - En “Settings” del servicio: **Root Directory** = `backend` (o el path donde está el backend si cambias la estructura).
   - **Build Command:** (Railway puede detectar Python y usar el Dockerfile si está en la raíz; si el Dockerfile está en la raíz y construye el backend, no hace falta root directory para el backend solo).  
   - Mejor: usar el `Dockerfile.backend` que ya tienes. En Railway configuras que el “source” sea la raíz del repo y el Dockerfile sea `Dockerfile.backend`.
   - **Variables:** Añade todas las env (ver lista abajo). La `DATABASE_URL` la copias del servicio Postgres de Railway.

5. **Desplegar el frontend**
   - Opción 1: Otro servicio en Railway que haga build de React y sirva estático (con un Dockerfile.frontend que ya tienes).
   - Opción 2: Frontend en Vercel/Netlify (conectas el mismo repo, build command `npm run build` en la carpeta `frontend`, y en las variables pones `REACT_APP_API_URL=https://tu-backend.up.railway.app`).

6. **Dominio en GoDaddy**
   - En Railway (o Render) asignas un “Custom Domain” (ej. `app.tudominio.com` o `tudominio.com`).
   - Te indican qué registro DNS crear (CNAME o A).
   - En GoDaddy: DNS → Añadir CNAME (ej. `app` → `tu-app.up.railway.app`) o la A que te den. En 5–60 min el dominio apunta a tu app con HTTPS.

7. **Variables de entorno en producción**
   - `SECRET_KEY`, `JWT_SECRET_KEY`: generados aleatorios.
   - `ENCRYPTION_KEY`: el que generaste con Fernet (para las API keys encriptadas).
   - `DATABASE_URL`: la que te da Railway/Render Postgres.
   - `FRONTEND_URL`: tu dominio real (ej. `https://app.tudominio.com`) para CORS y redirects.
   - Falabella: no hace falta si no usas Falabella en este deploy.
   - Mercado Libre: `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI` = **https://app.tudominio.com/mercado-libre/callback** (o la URL que use tu backend para el callback).

8. **Migraciones**
   - En Railway/Render sueles ejecutar migraciones en “Deploy” o con un comando one-off: desde la raíz del backend, `flask db upgrade` (o el comando que uses). Algunas plataformas permiten “Release Command”.

---

## 5. Variables de entorno (checklist)

```
# App
SECRET_KEY=<generar aleatorio>
JWT_SECRET_KEY=<generar aleatorio>
ENCRYPTION_KEY=<clave Fernet de 44 caracteres>
FLASK_ENV=production

# Base de datos (la da la plataforma)
DATABASE_URL=postgresql://...

# URLs (tras configurar dominio)
FRONTEND_URL=https://app.tudominio.com

# Mercado Libre (cuando crees la app en ML)
ML_CLIENT_ID=...
ML_CLIENT_SECRET=...
ML_REDIRECT_URI=https://app.tudominio.com/mercado-libre/callback
ML_AUTH_BASE=https://auth.mercadolibre.com.ar
```

Para Falabella/Haulmer las keys las guarda cada usuario en la app (encriptadas); no van en env del servidor salvo que quieras un valor por defecto.

---

## 6. Orden recomendado

1. Subir código a **GitHub**.
2. Elegir **Railway** o **Render** y conectar el repo.
3. Crear **PostgreSQL** y **Backend**; configurar variables; desplegar.
4. Crear **Frontend** (mismo repo o Vercel) con `REACT_APP_API_URL` apuntando al backend.
5. Probar con la URL que te dan (`.railway.app` o `.onrender.com`).
6. En **GoDaddy**, apuntar el dominio (CNAME o A) a esa URL.
7. En la plataforma, añadir **Custom Domain** y esperar HTTPS.
8. Cuando tengas la URL final, crear la app en **Mercado Libre** con esa Redirect URI y configurar `ML_*` en el backend.

No hace falta tener todo perfecto el primer día: puedes desplegar primero con la URL de Railway/Render y usar esa URL para ML; después cambias a tu dominio y actualizas solo la Redirect URI y `FRONTEND_URL`/CORS.
