# Integración Mercado Libre

## ¿Necesito la app en producción para crear la app en ML?

**No necesariamente.** Mercado Libre pide una **Redirect URI** (URL de redirección) al registrar la aplicación. Esa URL debe ser **HTTPS** y coincidir exactamente con la que uses en el flujo OAuth.

Opciones:

1. **Producción**  
   Cuando tengas dominio y HTTPS (ej. `https://tuapp.com`), registras en ML:  
   `https://tuapp.com/mercado-libre/callback`  
   y usas esa misma URL en el flujo de autorización.

2. **Desarrollo con túnel (sin producción)**  
   Usas un túnel HTTPS que apunta a tu máquina:
   - [ngrok](https://ngrok.com): `ngrok http 5000` → te da una URL tipo `https://abc123.ngrok.io`
   - Registras en ML: `https://abc123.ngrok.io/mercado-libre/callback`
   - Corres backend en local (puerto 5000); cuando el vendedor autoriza, ML redirige al túnel y tu backend recibe el `code` en `/mercado-libre/callback`.

3. **Staging / preview**  
   Un deploy temporal con HTTPS (Railway, Render, Fly.io, Vercel, etc.) con una URL fija (ej. `https://invoice-mvp-staging.up.railway.app`). Esa URL la registras en ML como Redirect URI y la usas hasta que tengas producción definitiva.

**Resumen:** No hace falta tener “todo” en producción; hace falta **una URL HTTPS** que ML pueda llamar para el callback. Esa URL puede ser producción, un túnel en desarrollo o un entorno staging.

## Crear la aplicación en Mercado Libre

1. Entra al [Dev Center](https://developers.mercadolibre.com.ar/devcenter) de tu país (ej. Argentina, Chile, México).
2. **Mis aplicaciones** → Crear aplicación.
3. Completa nombre, descripción, logo.
4. **Redirect URI:** la URL de callback de tu backend (ej. `https://tudominio.com/mercado-libre/callback` o la de ngrok/staging). Debe ser HTTPS y exacta.
5. Guardas y obtienes **App ID (client_id)** y **Secret Key (client_secret)**.

Configura en tu backend (variables de entorno):

- `ML_CLIENT_ID` = App ID  
- `ML_CLIENT_SECRET` = Secret Key  
- `ML_REDIRECT_URI` = misma URL registrada (ej. `https://tudominio.com/mercado-libre/callback`)

Para Chile: dominio `auth.mercadolibre.cl` y mismo flujo. La app puede estar creada en cualquier país; el usuario autoriza con su cuenta del sitio correspondiente.

## Flujo OAuth en esta app

1. El usuario (vendedor) en **Configuración** hace clic en “Conectar Mercado Libre”.
2. El frontend redirige a `GET /mercado-libre/auth` del backend.
3. El backend redirige al usuario a Mercado Libre (`auth.mercadolibre.xx/authorization?response_type=code&client_id=...&redirect_uri=...`).
4. El vendedor inicia sesión en ML y autoriza la app.
5. ML redirige a tu `ML_REDIRECT_URI` con `?code=...`.
6. El backend en `GET /mercado-libre/callback?code=...` intercambia el `code` por `access_token` y `refresh_token`, los guarda encriptados para ese usuario y redirige al frontend (ej. “Conexión exitosa”).
7. Para subir facturas se usa ese `access_token` (y, al expirar, el `refresh_token`).

## Límites API ML

- **Upload fiscal document:** 1 PDF por pack, máximo 1 MB. Opcional: 1 PDF + 1 XML.
- **No disponible** en Mercado Livre (Brasil).
- **Chile:** no aplica para envíos “Full” (fulfillment por ML).
