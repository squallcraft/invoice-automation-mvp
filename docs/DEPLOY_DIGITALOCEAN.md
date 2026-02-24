# Desplegar en DigitalOcean Droplet + dominio GoDaddy

Guía para poner en producción la app de boletas/facturas en un **Droplet** de DigitalOcean y usar tu **dominio de GoDaddy** con HTTPS.

---

## Qué tienes ya

- **Dominio** en GoDaddy (ej. `tudominio.com`)
- **Droplets** en DigitalOcean
- **Código** en GitHub: `squallcraft/invoice-automation-mvp`

---

## Resumen de pasos

1. Crear/configurar un Droplet (Docker + Docker Compose).
2. Clonar el repo, configurar variables de entorno y levantar la app con `docker-compose`.
3. Instalar Nginx y Certbot en el Droplet; configurar proxy y HTTPS.
4. En GoDaddy, apuntar el dominio (A) a la IP del Droplet.
5. Crear la app en Mercado Libre con la Redirect URI de producción y configurar `ML_*` en el backend.
6. Ejecutar migraciones de la base de datos.

---

## 1. Droplet en DigitalOcean

### 1.1 Crear el Droplet (si aún no lo tienes)

- **Imagen:** Ubuntu 22.04 LTS.
- **Plan:** Mínimo 1 GB RAM (recomendado 2 GB para Docker + Postgres + app).
- **Región:** La más cercana a tus usuarios.
- **Autenticación:** SSH key (recomendado) o contraseña.
- Anota la **IP pública** del Droplet (ej. `164.92.xxx.xxx`).

### 1.2 Conectarte por SSH

```bash
ssh root@TU_IP_DEL_DROPLET
```

### 1.3 Instalar Docker y Docker Compose

```bash
apt update && apt install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Comprobar:

```bash
docker --version
docker compose version
```

### 1.4 (Opcional) Usuario no root

```bash
adduser deploy
usermod -aG docker deploy
# Configurar SSH con tu clave para deploy
```

A partir de aquí puedes usar `deploy` en lugar de `root`; si sigues como root, los comandos son los mismos.

---

## 2. Clonar el proyecto y configurar entorno

### 2.1 Clonar el repo

```bash
cd /opt   # o /home/deploy si usas usuario deploy
git clone https://github.com/squallcraft/invoice-automation-mvp.git
cd invoice-automation-mvp
```

### 2.2 Archivo de variables de entorno

Copia el ejemplo y edita con tus valores de producción:

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Variables mínimas para producción (sustituir valores):

```env
FLASK_APP=app.app
FLASK_ENV=production
SECRET_KEY=genera-una-clave-aleatoria-larga
JWT_SECRET_KEY=otra-clave-aleatoria-larga
ENCRYPTION_KEY=tu-clave-fernet-44-chars

DATABASE_URL=postgresql://postgres:postgres@db:5432/invoice_automation

FRONTEND_URL=https://app.tudominio.com
ML_CLIENT_ID=tu-app-id-ml
ML_CLIENT_SECRET=tu-secret-ml
ML_REDIRECT_URI=https://app.tudominio.com/mercado-libre/callback
ML_AUTH_BASE=https://auth.mercadolibre.com.ar
```

- **SECRET_KEY / JWT_SECRET_KEY:** genera con `openssl rand -hex 32`.
- **ENCRYPTION_KEY:** el que generaste con `scripts/generate_fernet_key.py` (debe ser el mismo que usas para descifrar keys guardadas).
- **FRONTEND_URL / ML_REDIRECT_URI:** usa tu dominio real (ej. `https://app.tudominio.com`). La Redirect URI debe coincidir **exactamente** con la que registres en la app de Mercado Libre.

En el Droplet, `DATABASE_URL` puede quedarse como arriba porque el servicio se llama `db` dentro de la red de Docker.

### 2.3 Levantar la app con Docker Compose

Desde la raíz del proyecto:

```bash
docker compose up -d --build
```

Comprobar que los contenedores estén arriba:

```bash
docker compose ps
```

Deberías ver `db`, `backend` y `frontend` en estado running.

### 2.4 Migraciones de base de datos

```bash
docker compose exec backend flask db upgrade
```

### 2.5 Probar que responde (solo desde el servidor)

```bash
curl -s http://localhost:5000/health
# {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
# 200
```

---

## 3. Nginx + HTTPS en el Droplet

Vas a poner **Nginx** en el host (no dentro de Docker) para recibir tráfico en 80/443 y hacer proxy al frontend (puerto 3000) y al backend (puerto 5000). Luego Certbot generará el certificado SSL.

### 3.1 Instalar Nginx y Certbot

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 3.2 Configuración de Nginx (antes de SSL)

Crea un sitio para tu dominio (sustituye `app.tudominio.com` por tu subdominio o dominio):

```bash
nano /etc/nginx/sites-available/invoice-app
```

Contenido (reemplaza `app.tudominio.com` por tu dominio):

```nginx
server {
    listen 80;
    server_name app.tudominio.com;

    location /api {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activar el sitio y recargar Nginx:

```bash
ln -s /etc/nginx/sites-available/invoice-app /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 3.3 Obtener certificado SSL con Certbot

```bash
certbot --nginx -d app.tudominio.com
```

Sigue las preguntas (email, aceptar términos). Certbot modificará la config de Nginx para escuchar en 443 y usar el certificado. Renovación automática ya queda configurada.

### 3.4 Firewall

Abre solo SSH, HTTP y HTTPS:

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
ufw status
```

---

## 4. Dominio en GoDaddy

1. Entra en **GoDaddy** → **Mis Productos** → tu dominio → **Administrar DNS** (o **DNS**).
2. Crea un registro **A**:
   - **Nombre:** `app` (para `app.tudominio.com`) o `@` (para la raíz `tudominio.com`).
   - **Valor / Apunta a:** la **IP del Droplet** (ej. `164.92.xxx.xxx`).
   - TTL: 600 o por defecto.
3. Guarda los cambios. La propagación puede tardar unos minutos (hasta 1 hora).

Si usas `app.tudominio.com`, el nombre del registro es `app`. Si quieres usar solo `tudominio.com`, el nombre es `@`.

---

## 5. Mercado Libre (para el flujo de ML)

1. Entra en [Desarrolladores de Mercado Libre](https://developers.mercadolibre.com.ar/) y tu aplicación.
2. En **URLs de redirección**, añade exactamente:
   `https://app.tudominio.com/mercado-libre/callback`
3. Guarda.
4. En el `.env` del backend (en el Droplet) ya debes tener:
   - `ML_REDIRECT_URI=https://app.tudominio.com/mercado-libre/callback`
   - `ML_CLIENT_ID` y `ML_CLIENT_SECRET` de esa app.
5. Reinicia el backend para que cargue las variables:
   ```bash
   docker compose restart backend
   ```

---

## 6. Checklist final

- [ ] Droplet creado, Docker y Docker Compose instalados.
- [ ] Repo clonado, `backend/.env` configurado con SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY, DATABASE_URL, FRONTEND_URL, ML_*.
- [ ] `docker compose up -d --build` y `docker compose exec backend flask db upgrade`.
- [ ] Nginx instalado, sitio configurado (proxy a 3000 y 5000), Certbot ejecutado para HTTPS.
- [ ] UFW: OpenSSH + Nginx Full.
- [ ] GoDaddy: registro A (app o @) apuntando a la IP del Droplet.
- [ ] App ML: Redirect URI = `https://app.tudominio.com/mercado-libre/callback`.
- [ ] Probar en el navegador: `https://app.tudominio.com` (login, flujo Mercado Libre).

---

## Comandos útiles después del despliegue

```bash
# Ver logs
docker compose logs -f backend
docker compose logs -f frontend

# Reiniciar todo
docker compose restart

# Actualizar código y redesplegar
cd /opt/invoice-automation-mvp
git pull
docker compose up -d --build
docker compose exec backend flask db upgrade
```

Si algo falla, revisa logs de Nginx (`/var/log/nginx/error.log`) y del backend (`docker compose logs backend`).
