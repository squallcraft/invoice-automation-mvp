# Despliegue paso a paso (for dummies)

Guía muy simple: copia, pega y cambia solo lo que diga **TU_XXX**. No hace falta ser técnico.

---

## Qué necesitas tener antes

- Cuenta en **DigitalOcean** (para el servidor).
- Un **dominio** (ej. en GoDaddy) y poder editar el DNS.
- **5 minutos** para generar 3 claves en tu computadora (te diré cómo).

---

## PASO 1 – Crear el servidor (Droplet)

1. Entra a **https://cloud.digitalocean.com** e inicia sesión.
2. Menú izquierdo → **Droplets** → **Create Droplet**.
3. **Imagen:** Ubuntu 22.04 (LTS).
4. **Tamaño:** el más barato (1 GB RAM).
5. **Región:** la más cercana a ti.
6. **Autenticación:** Password y anota una contraseña segura (la usarás para entrar al servidor).
7. **Create Droplet**.
8. Cuando termine, anota la **IP** que te muestra (ej. `164.92.123.45`). Es **TU_IP**.

---

## PASO 2 – Entrar al servidor desde tu computadora

1. Abre la **Terminal** (Mac: Cmd+Espacio, escribe “Terminal”, Enter).
2. Escribe (cambia **TU_IP** por la IP del Paso 1):

```bash
ssh root@TU_IP
```

3. Si pregunta “Are you sure…?”, escribe **yes** y Enter.
4. Pide contraseña: pega la del Droplet (no se verá nada) y Enter.

Cuando veas algo como `root@nombre:~#` **ya estás dentro del servidor**. El resto de comandos se pegan aquí.

---

## PASO 3 – Instalar Docker

Pega **cada bloque**, Enter, y espera a que termine antes del siguiente.

```bash
apt update && apt install -y ca-certificates curl gnupg
```

```bash
install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && chmod a+r /etc/apt/keyrings/docker.gpg
```

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
```

```bash
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

(Si pregunta Y/n, escribe **Y** y Enter.)

Comprueba: `docker --version`. Debe salir una versión. Sigue.

---

## PASO 4 – Bajar el proyecto al servidor

```bash
cd /opt
git clone https://github.com/squallcraft/invoice-automation-mvp.git
cd invoice-automation-mvp
```

(Si tu proyecto está en **otro repo**, cambia la URL del `git clone`.)

---

## PASO 5 – Generar las 3 claves (en tu Mac, en otra ventana de Terminal)

**No cierres** la sesión del servidor. Abre **otra ventana de Terminal en tu Mac**.

En esa ventana (en tu Mac), ejecuta **uno por uno** y **anota** cada resultado:

**Clave 1 (SECRET_KEY):**
```bash
openssl rand -hex 32
```

**Clave 2 (JWT_SECRET_KEY):**
```bash
openssl rand -hex 32
```

**Clave 3 (ENCRYPTION_KEY):**  
Si tienes el proyecto en tu Mac:
```bash
cd /ruta/donde/está/invoice-automation-mvp
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Copia la línea que salga (unos 44 caracteres).

Si no tienes Python en tu Mac, puedes usar otra clave de 44 caracteres en base64 (o genera una con `openssl rand -base64 32` y úsala; el backend acepta una clave que Fernet pueda usar).

Vuelve a la Terminal **donde estás conectado al servidor** (Paso 2).

---

## PASO 6 – Crear y editar el archivo .env en el servidor

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

En nano, **cambia** (usa las flechas y borra/pega):

- `SECRET_KEY=...` → pega tu **Clave 1**.
- Añade una línea: `JWT_SECRET_KEY=` y pega tu **Clave 2**.
- `ENCRYPTION_KEY=...` → pega tu **Clave 3**.

Luego **ajusta** estas líneas (cambia **TU_DOMINIO** por tu dominio real, ej. `boletas.cl`):

- `FLASK_ENV=production`
- `DATABASE_URL=postgresql://postgres:postgres@db:5432/invoice_automation`
- `FRONTEND_URL=https://app.TU_DOMINIO`
- `ML_REDIRECT_URI=https://app.TU_DOMINIO/api/mercado-libre/callback`
- `ML_AUTH_BASE=https://auth.mercadolibre.com.ar`

(Si usas la raíz del dominio sin “app”, pon `https://TU_DOMINIO` donde corresponda.)

Deja por ahora:
- `ML_CLIENT_ID=` y `ML_CLIENT_SECRET=` vacíos (los rellenarás después de crear la app en Mercado Libre).

**Guardar en nano:** Ctrl+O, Enter. **Salir:** Ctrl+X.

---

## PASO 7 – Levantar la app con Docker

En el servidor (en `/opt/invoice-automation-mvp`):

```bash
docker compose up -d --build
```

Espera 2–5 minutos. Luego:

```bash
docker compose exec backend flask db upgrade
```

Si no hay errores, la base de datos está lista.

---

## PASO 8 – Instalar Nginx y Certbot

```bash
apt install -y nginx certbot python3-certbot-nginx
```
(Si pregunta Y/n, **Y** y Enter.)

---

## PASO 9 – Configurar Nginx (cambia app.TU_DOMINIO por tu dominio)

```bash
nano /etc/nginx/sites-available/invoice-app
```

Borra todo y pega esto (cambia **app.tudominio.com** por tu dominio, ej. `app.boletas.cl`):

```
server {
    listen 80;
    server_name app.tudominio.com;

    location /api/ {
        proxy_pass http://127.0.0.1:5000/;
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

Guardar: Ctrl+O, Enter. Salir: Ctrl+X.

Activar y recargar:

```bash
ln -sf /etc/nginx/sites-available/invoice-app /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

---

## PASO 10 – Abrir el firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw enable
```
(Si pregunta, **Y** y Enter.)

---

## PASO 11 – Apuntar tu dominio al servidor (GoDaddy u otro)

1. Entra a tu proveedor de dominio (ej. GoDaddy) → **DNS** o **Administrar DNS**.
2. **Añadir registro:** tipo **A**.
3. **Nombre:** si quieres **app.tudominio.com** → escribe **app**. (Si quieres tudominio.com sin “app”, usa **@** según tu proveedor.)
4. **Valor / Apunta a:** la **IP del Droplet** (la del Paso 1).
5. Guardar.

La propagación puede tardar 5–60 minutos.

---

## PASO 12 – Obtener el certificado HTTPS

Cuando el dominio ya apunte al servidor (puedes probar abriendo http://app.TU_DOMINIO), en el servidor ejecuta (cambia por tu dominio):

```bash
certbot --nginx -d app.TU_DOMINIO
```

Pon tu email, acepta términos (Y). Si todo va bien, dirá “Successfully received certificate”.

---

## PASO 13 – Configurar Mercado Libre (para “Conectar con Mercado Libre”)

1. Entra a **https://developers.mercadolibre.com.ar** (o tu país) → **Mis aplicaciones**.
2. Abre tu app (o crea una).
3. En **URLs de redirección** añade **exactamente** (con tu dominio):
   - `https://app.TU_DOMINIO/api/mercado-libre/callback`
4. Guarda. Copia el **App ID** y el **Secret**.

En el servidor:

```bash
cd /opt/invoice-automation-mvp
nano backend/.env
```

Pega:
- En `ML_CLIENT_ID=` tu **App ID**.
- En `ML_CLIENT_SECRET=` tu **Secret**.

Guardar (Ctrl+O, Enter) y salir (Ctrl+X). Reinicia el backend:

```bash
docker compose restart backend
```

---

## PASO 14 – Probar

1. En el navegador abre **https://app.TU_DOMINIO** (con tu dominio).
2. Deberías ver la pantalla de **Login / Registro**.
3. Regístrate, entra, ve a **Configuración** y prueba **Conectar con Mercado Libre**.

---

## Resumen rápido (lista de pasos)

| # | Dónde | Qué hacer |
|---|--------|-----------|
| 1 | DigitalOcean | Crear Droplet Ubuntu 22.04, anotar IP |
| 2 | Terminal (Mac) | `ssh root@TU_IP` |
| 3 | Servidor | Instalar Docker (4 bloques de comandos) |
| 4 | Servidor | `git clone` del proyecto en `/opt` |
| 5 | Mac (otra Terminal) | Generar SECRET_KEY, JWT_SECRET_KEY, ENCRYPTION_KEY |
| 6 | Servidor | `nano backend/.env` y pegar claves + TU_DOMINIO, ML_REDIRECT_URI |
| 7 | Servidor | `docker compose up -d --build` y `flask db upgrade` |
| 8 | Servidor | `apt install nginx certbot python3-certbot-nginx` |
| 9 | Servidor | Crear sitio Nginx con `server_name` y `location /api/` y `location /` |
| 10 | Servidor | `ufw allow` y `ufw enable` |
| 11 | GoDaddy/DNS | Registro A: nombre `app`, valor = IP del Droplet |
| 12 | Servidor | `certbot --nginx -d app.TU_DOMINIO` |
| 13 | Mercado Libre + servidor | Añadir redirect URI, copiar App ID y Secret a `backend/.env`, `docker compose restart backend` |
| 14 | Navegador | Abrir https://app.TU_DOMINIO y probar login + ML |

---

## Si algo falla

- **No entro por SSH:** Comprueba la IP, que el Droplet esté encendido y la contraseña.
- **Error con Docker:** Revisa que en `backend/.env` estén las 3 claves y sin espacios raros.
- **La web no carga:** Espera hasta 1 hora tras cambiar el DNS. Comprueba que el registro A apunte a la IP correcta.
- **Certbot falla:** Comprueba que el dominio ya resuelva a tu servidor (`ping app.TU_DOMINIO`) y que en Nginx `server_name` sea exactamente tu dominio.
- **Mercado Libre no vuelve a la app:** La URL de redirección en ML debe ser **exactamente** `https://app.TU_DOMINIO/api/mercado-libre/callback` (con `/api/`).

Si tienes un mensaje de error concreto, anótalo y el paso en el que aparece para poder afinar.
