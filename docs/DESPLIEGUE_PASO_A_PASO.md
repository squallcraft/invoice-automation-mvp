# Desplegar la app – Paso a paso (guía sencilla)

Esta guía está pensada para seguirla **al pie de la letra**, paso por paso. No hace falta ser desarrollador.

**Antes de empezar, ten a mano:**
- Tu **dominio de GoDaddy** (ej. `mitienda.com`).
- Acceso a **DigitalOcean** (cuenta y posibilidad de crear un Droplet).
- Tu **email** y **contraseña** de cada sitio cuando te los pida.

Decide cómo quieres que se llame la app en internet:
- Opción A: **app.midominio.com** (recomendado) → en la guía usaremos “app” como nombre.
- Opción B: **midominio.com** (la raíz del dominio).

En los pasos diré **“tu-dominio”** o **“TU_DOMINIO”**: cámbialo siempre por tu dominio real (ej. si tu dominio es `boletas.cl`, donde diga `app.tudominio.com` tú pones `app.boletas.cl`).

---

# PARTE 1 – Crear el servidor (Droplet) en DigitalOcean

## Paso 1.1 – Entrar a DigitalOcean

1. Abre el navegador y ve a: **https://cloud.digitalocean.com**
2. Inicia sesión con tu cuenta.
3. Si te pide verificación, complétala.

**Deberías ver:** el panel de DigitalOcean (menú a la izquierda, etc.).

---

## Paso 1.2 – Crear un nuevo Droplet

1. En el menú izquierdo, haz clic en **“Droplets”**.
2. Haz clic en el botón **“Create Droplet”** (o “Create” → “Droplets”).
3. En **“Choose an image”** (elegir imagen):
   - Elige la pestaña **“Distribution”**.
   - Selecciona **“Ubuntu”** y la versión **22.04 (LTS)**.
4. En **“Choose size”** (tamaño):
   - Elige el plan más barato que diga **1 GB RAM** (o 2 GB si lo prefieres).
5. En **“Choose a datacenter region”**:
   - Elige la región más cercana a ti (ej. Nueva York, San Francisco, etc.).
6. En **“Authentication”** (autenticación):
   - Si ya tienes una **SSH key** en DigitalOcean, selecciónala.
   - Si no, elige **“Password”** y inventa una contraseña **muy segura**. **Anótala en un lugar seguro** (la usarás para entrar al servidor).
7. En **“Hostname”** puedes dejar algo como: `invoice-app` (o el nombre que quieras para identificar el servidor).
8. Haz clic en **“Create Droplet”**.

**Deberías ver:** que el Droplet se está creando (un punto o “Spinning up…”). Espera 1–2 minutos hasta que aparezca una **IP** (cuatro números separados por puntos, ej. `164.92.123.45`).

---

## Paso 1.3 – Anotar la IP del Droplet

1. En la lista de Droplets, haz clic en el Droplet que acabas de crear (nombre o IP).
2. Arriba verás **“Public IP”** o “IP address”. Es algo como: **164.92.123.45**.
3. **Cópiala y guárdala** en un bloc de notas. La usarás como **“LA_IP_DE_TU_DROPLET”** en los siguientes pasos.

**Ejemplo:** si tu IP es `164.92.123.45`, cada vez que en la guía diga “LA_IP_DE_TU_DROPLET” tú usarás `164.92.123.45`.

---

# PARTE 2 – Conectarte al servidor desde tu Mac

## Paso 2.1 – Abrir la Terminal en tu Mac

1. Pulsa **Cmd + Espacio** (para abrir Spotlight).
2. Escribe: **Terminal**.
3. Pulsa **Enter** para abrir la aplicación “Terminal”.

**Deberías ver:** una ventana con texto en blanco y negro y una línea que termina con algo como `%` o `$`. Ahí es donde escribirás los comandos.

---

## Paso 2.2 – Conectarte al Droplet por SSH

1. En la Terminal, escribe **exactamente** (cambia `LA_IP_DE_TU_DROPLET` por la IP que anotaste):

```bash
ssh root@LA_IP_DE_TU_DROPLET
```

Ejemplo: si tu IP es `164.92.123.45`, escribirías:

```bash
ssh root@164.92.123.45
```

2. Pulsa **Enter**.
3. Si sale un mensaje tipo “Are you sure you want to continue connecting?” escribe **yes** y Enter.
4. Si te pide **password**, escribe la contraseña del Droplet (la que pusiste al crearlo). **Al escribir no se verá nada** (ni asteriscos); es normal. Escribe y pulsa Enter.

**Deberías ver:** que la línea de la Terminal cambia y ahora empieza por algo como `root@invoice-app:~#`. Eso significa que **ya estás dentro del servidor**. Los siguientes comandos se ejecutan en el servidor, no en tu Mac.

---

## Paso 2.3 – Instalar Docker (programa que ejecuta la app)

Vas a pegar **varios bloques de comandos** uno tras otro. Después de cada bloque, pulsa **Enter** y espera a que termine (puede tardar 1–2 minutos).

**Bloque 1** – Pega esto y Enter:

```bash
apt update && apt install -y ca-certificates curl gnupg
```

Cuando termine (vuelva a salir la línea con `#`), pega el **Bloque 2**:

```bash
install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && chmod a+r /etc/apt/keyrings/docker.gpg
```

Cuando termine, **Bloque 3**:

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Cuando termine, **Bloque 4**:

```bash
apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Si pregunta “Do you want to continue? [Y/n]”, escribe **Y** y Enter.

**Deberías ver:** al final que se instalaron paquetes y vuelve a aparecer la línea `root@...`.

**Comprobar:** escribe esto y Enter:

```bash
docker --version
```

Deberías ver algo como: `Docker version 24.x.x`. Si lo ves, sigue al Paso 2.4.

---

## Paso 2.4 – Descargar el proyecto (clonar desde GitHub)

1. Entra en la carpeta donde guardaremos el proyecto:

```bash
cd /opt
```

2. Descarga el código del proyecto:

```bash
git clone https://github.com/squallcraft/invoice-automation-mvp.git
```

3. Entra en la carpeta del proyecto:

```bash
cd invoice-automation-mvp
```

**Deberías ver:** que se descargan archivos y al final vuelve la línea `#`. Si escribes `ls` y Enter, verás carpetas como `backend`, `frontend`, `docs`.

---

# PARTE 3 – Configurar la app en el servidor

## Paso 3.1 – Crear el archivo de configuración (.env)

1. Copia el archivo de ejemplo:

```bash
cp backend/.env.example backend/.env
```

2. Abre el archivo para editarlo:

```bash
nano backend/.env
```

**Deberías ver:** un editor de texto dentro de la Terminal con varias líneas (FLASK_APP, SECRET_KEY, etc.).

---

## Paso 3.2 – Generar claves secretas (en tu Mac, en otra ventana de Terminal)

**No cierres** la sesión SSH. Abre **otra ventana de Terminal en tu Mac** (Terminal → New Window o Cmd+N).

En esa **nueva** ventana (en tu Mac), escribe y ejecuta **una por una**:

Para SECRET_KEY:

```bash
openssl rand -hex 32
```

Copia el resultado (una línea larga de letras y números). Es tu **SECRET_KEY**.

Para JWT_SECRET_KEY (otra clave distinta):

```bash
openssl rand -hex 32
```

Copia ese resultado. Es tu **JWT_SECRET_KEY**.

Si ya tienes una **ENCRYPTION_KEY** (la generaste antes con el script de Fernet en el proyecto), úsala. Si no, en la misma Terminal de tu Mac, desde la carpeta del proyecto:

```bash
cd /Users/oscarguzman/invoice-automation-mvp
python3 scripts/generate_fernet_key.py
```

Copia la línea que salga. Es tu **ENCRYPTION_KEY**.

Vuelve a la ventana de Terminal donde estabas conectado al servidor (SSH).

---

## Paso 3.3 – Editar el archivo .env en el servidor

En la Terminal **del servidor** (donde tienes abierto `nano backend/.env`):

1. Usa las **flechas del teclado** para moverte. **Borra** los valores de ejemplo y **pega** los que generaste:
   - Donde diga `your-secret-key-change-in-production` → pega tu **SECRET_KEY**.
   - Añade una línea: `JWT_SECRET_KEY=` y pega tu **JWT_SECRET_KEY**.
   - Donde diga `generate-with-fernet-key.py` → pega tu **ENCRYPTION_KEY** (la de 44 caracteres).

2. Cambia estas líneas para que queden así (**cambia TU_DOMINIO por tu dominio real**, ej. `boletas.cl`):

   - `FLASK_ENV=production`
   - **No pongas `DATABASE_URL`** en este archivo cuando uses Docker; el `docker-compose.yml` ya la define (postgres:postgres@db).
   - `FRONTEND_URL=https://app.TU_DOMINIO`
   - `ML_REDIRECT_URI=https://app.TU_DOMINIO/api/mercado-libre/callback`
   - `ML_AUTH_BASE=https://auth.mercadolibre.com.ar`

   Si usas la raíz del dominio (midominio.com sin “app”), entonces:
   - `FRONTEND_URL=https://TU_DOMINIO`
   - `ML_REDIRECT_URI=https://TU_DOMINIO/api/mercado-libre/callback`

3. **ML_CLIENT_ID** y **ML_CLIENT_SECRET**: déjalos vacíos por ahora (ej. `ML_CLIENT_ID=` y `ML_CLIENT_SECRET=`). Los rellenarás cuando tengas la app de Mercado Libre y la URL funcionando (Parte 5).

4. Guardar y salir de nano:
   - Pulsa **Ctrl+O** (para guardar), luego **Enter**.
   - Pulsa **Ctrl+X** (para salir).

**Deberías ver:** que vuelves a la línea de comandos `#` en la carpeta `invoice-automation-mvp`.

---

## Paso 3.4 – Levantar la app con Docker

Desde la carpeta del proyecto en el servidor (si no estás, escribe `cd /opt/invoice-automation-mvp`):

```bash
docker compose up -d --build
```

**Puede tardar varios minutos** (2–5). Verás que descarga cosas y construye la app.

**Deberías ver:** al final algo como “done” o que vuelve la línea `#` sin errores en rojo.

Comprobar que los contenedores están activos:

```bash
docker compose ps
```

**Deberías ver:** tres filas, una para `db`, una para `backend`, una para `frontend`, y en “Status” algo como “Up” o “running”.

---

## Paso 3.5 – Ejecutar las migraciones de la base de datos

Solo este comando:

```bash
docker compose exec backend flask db upgrade
```

**Deberías ver:** unas líneas que dicen “Running upgrade” y al final la línea `#` de nuevo. Si sale algún error, anótalo y no sigas hasta resolverlo.

---

# PARTE 4 – Instalar Nginx y poner HTTPS (certificado)

## Paso 4.1 – Instalar Nginx y Certbot

En el servidor (misma sesión SSH):

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Si pregunta “Do you want to continue? [Y/n]”, escribe **Y** y Enter.

---

## Paso 4.2 – Crear el archivo de configuración de Nginx

1. Abre el editor para crear el archivo (cambia **app.TU_DOMINIO** por tu dominio real, ej. `app.boletas.cl`):

```bash
nano /etc/nginx/sites-available/invoice-app
```

2. **Borra** todo lo que haya y **pega** exactamente este bloque (y cambia **app.tudominio.com** por tu dominio, ej. `app.boletas.cl`):

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

3. Guardar: **Ctrl+O**, Enter. Salir: **Ctrl+X**.

---

## Paso 4.3 – Activar el sitio y recargar Nginx

Ejecuta estos dos comandos, uno tras otro:

```bash
ln -s /etc/nginx/sites-available/invoice-app /etc/nginx/sites-enabled/
```

```bash
nginx -t && systemctl reload nginx
```

**Deberías ver:** “syntax is ok” y “test is successful”, y luego que Nginx se recarga.

---

## Paso 4.4 – Abrir el firewall

Ejecuta estos, uno por uno (si pregunta, escribe **Y** y Enter):

```bash
ufw allow OpenSSH
```

```bash
ufw allow 'Nginx Full'
```

```bash
ufw enable
```

```bash
ufw status
```

**Deberías ver:** que “OpenSSH” y “Nginx Full” están “ALLOW”.

---

# PARTE 5 – Apuntar tu dominio (GoDaddy) al servidor

**Importante:** Haz esto **después** de tener el servidor y Nginx listos. Así cuando pongas el dominio, ya habrá algo respondiendo.

## Paso 5.1 – Entrar a GoDaddy y al DNS

1. Abre el navegador y ve a **https://www.godaddy.com**
2. Inicia sesión.
3. Ve a **Mis Productos** (o “My Products”).
4. Busca tu dominio y haz clic en **“DNS”** o **“Administrar DNS”** (o “Manage DNS”).

**Deberías ver:** una tabla con registros DNS (A, CNAME, etc.).

---

## Paso 5.2 – Añadir el registro A

1. Busca el botón **“Añadir”** o **“Add”** (o “Add record” / “Agregar registro”).
2. Tipo de registro: **A**.
3. **Nombre / Host / Name:**
   - Si quieres que la app sea **app.tudominio.com** → escribe: **app**
   - Si quieres que sea **tudominio.com** (sin “app”) → deja en blanco o escribe **@** (según lo que muestre GoDaddy).
4. **Valor / Apunta a / Points to:** la **IP de tu Droplet** (la que anotaste en el Paso 1.3). Solo números y puntos, ej. `164.92.123.45`.
5. TTL: déjalo por defecto (ej. 600 o 1 hora).
6. Guarda el registro.

**Deberías ver:** el nuevo registro A en la lista. La propagación puede tardar **5–60 minutos**. Puedes seguir con el siguiente paso mientras tanto.

---

# PARTE 6 – Obtener el certificado HTTPS (Certbot)

**Recomendación:** Esperar 10–15 minutos después de haber guardado el registro A en GoDaddy, para que el dominio ya apunte al servidor.

En la Terminal **del servidor** (SSH), ejecuta (cambia **app.TU_DOMINIO** por tu dominio real):

```bash
certbot --nginx -d app.TU_DOMINIO
```

Ejemplo: si tu dominio es `app.boletas.cl`:

```bash
certbot --nginx -d app.boletas.cl
```

1. Si pide **email**, escribe tu correo y Enter.
2. Acepta los **términos** (escribe Y).
3. Si pregunta si quieres recibir noticias, puedes poner N.
4. Si todo va bien, dirá “Successfully received certificate”.

**Si falla** diciendo que no puede verificar el dominio, suele ser porque el dominio aún no apunta al servidor. Espera un poco más y vuelve a ejecutar el mismo comando.

---

# PARTE 7 – Configurar Mercado Libre

## Paso 7.1 – App en Mercado Libre

1. Entra en **https://developers.mercadolibre.com.ar** (o el país que uses).
2. Inicia sesión y ve a **Mis aplicaciones** (o “My applications”).
3. Abre tu aplicación (o crea una si no tienes).
4. Busca **“URLs de redirección”** o “Redirect URIs”.
5. Añade **exactamente** esta URL (cambia por tu dominio real):
   - Si usas app: **https://app.TU_DOMINIO/api/mercado-libre/callback**
   - Ejemplo: **https://app.boletas.cl/api/mercado-libre/callback**
6. Guarda los cambios.

---

## Paso 7.2 – Copiar App ID y Secret

En la misma página de la aplicación de Mercado Libre:

1. Copia el **App ID** (o Application ID).
2. Copia el **Secret** (o Secret Key). A veces hay que hacer clic en “Ver” para verlo.

---

## Paso 7.3 – Poner ML_CLIENT_ID y ML_CLIENT_SECRET en el servidor

En la Terminal del servidor (SSH), entra al proyecto y abre el .env:

```bash
cd /opt/invoice-automation-mvp
nano backend/.env
```

1. Busca la línea `ML_CLIENT_ID=` y después del `=` pega tu **App ID** (sin espacios).
2. Busca `ML_CLIENT_SECRET=` y después del `=` pega tu **Secret** (sin espacios).
3. Guardar: **Ctrl+O**, Enter. Salir: **Ctrl+X**.

Reinicia el backend para que cargue los cambios:

```bash
docker compose restart backend
```

**Deberías ver:** que el contenedor `backend` se reinicia.

---

# PARTE 8 – Probar que todo funciona

1. Abre el navegador en tu Mac.
2. Escribe en la barra de direcciones (con tu dominio real):
   - **https://app.TU_DOMINIO**  
   Ejemplo: **https://app.boletas.cl**
3. Pulsa Enter.

**Deberías ver:** la pantalla de login (o registro) de tu app. Si ves un candado en la barra de direcciones, el HTTPS está bien.

4. Regístrate o inicia sesión.
5. Ve a la parte de **Mercado Libre** (o integración) y prueba el flujo de conectar cuenta. Te debería redirigir a Mercado Libre y luego volver a tu app.

Si algo no carga o sale error, anota el mensaje exacto y en qué paso estabas (ej. “al abrir https://app.boletas.cl sale error 502”). Con eso se puede afinar el siguiente paso.

---

# Resumen rápido (para cuando ya hayas hecho todo una vez)

| Dónde       | Qué hiciste |
|------------|-------------|
| DigitalOcean | Crear Droplet Ubuntu 22.04, anotar IP. |
| Terminal (Mac) | `ssh root@LA_IP` para entrar al servidor. |
| Servidor   | Instalar Docker, clonar repo, configurar `.env`, `docker compose up -d --build`, `flask db upgrade`, Nginx, Certbot. |
| GoDaddy    | Registro A (nombre `app` o `@`) apuntando a la IP del Droplet. |
| Mercado Libre | Redirect URI = `https://app.TU_DOMINIO/api/mercado-libre/callback`, copiar App ID y Secret al `.env`. |

---

# Si algo sale mal

- **No puedo conectarme por SSH:** Revisa que la IP sea correcta, que el Droplet esté “On”, y que hayas puesto bien la contraseña (o la SSH key).
- **Error al hacer `docker compose up`:** Revisa que en `backend/.env` no falte ninguna línea y que no haya espacios raros. SECRET_KEY, JWT_SECRET_KEY y ENCRYPTION_KEY deben tener valor.
- **La web no carga con mi dominio:** Espera hasta 1 hora tras cambiar el DNS en GoDaddy. Comprueba que el registro A apunte a la IP correcta.
- **Certbot falla:** Asegúrate de que el registro A en GoDaddy ya esté activo y que en Nginx el `server_name` sea exactamente tu dominio (ej. `app.boletas.cl`).

Cuando tengas un error concreto (y el mensaje que ves), se puede ir paso a paso para solucionarlo.
