# Subir el proyecto a GitHub – Paso a paso

Puedes hacerlo **desde Cursor** (con la vista de Git integrada) o **desde la terminal**. Aquí tienes las dos formas.

---

## Antes de empezar: Inicializar Git en tu proyecto (solo una vez)

Si nunca has usado Git en esta carpeta, haz esto **una sola vez** en la terminal de Cursor (**Terminal → New Terminal**):

```bash
cd /Users/oscarguzman/invoice-automation-mvp
git init
```

Después de eso, en Cursor verás los archivos en el panel **Source Control** (icono de ramas a la izquierda).

---

## Parte 1: Crear una cuenta y un repositorio en GitHub (en el navegador)

1. **Cuenta en GitHub**  
   Si no tienes: entra a [github.com](https://github.com), “Sign up” y crea la cuenta.

2. **Nuevo repositorio**  
   - Arriba a la derecha: **“+”** → **“New repository”**.  
   - **Repository name:** por ejemplo `invoice-automation-mvp`.  
   - **Description:** opcional (ej. “MVP emisión boletas/facturas + Falabella + ML”).  
   - **Public.**  
   - **No** marques “Add a README”, “Add .gitignore” ni “Choose a license” (el proyecto ya tiene archivos).  
   - Clic en **“Create repository”**.

3. **Anota la URL del repo**  
   Te saldrá algo como:  
   `https://github.com/TU_USUARIO/invoice-automation-mvp.git`  
   (o con SSH: `git@github.com:TU_USUARIO/invoice-automation-mvp.git`).  
   La usarás en los pasos siguientes.

---

## Parte 2: Opción A – Desde Cursor (vista de Git)

### 2.1 Abrir el panel de control de código fuente

- En la barra izquierda de Cursor haz clic en el icono de **ramas** (Source Control).  
- O atajo: **Ctrl+Shift+G** (Windows/Linux) / **Cmd+Shift+G** (Mac).

### 2.2 Inicializar el repositorio (si aún no está inicializado)

- Si ves el botón **“Initialize Repository”**, haz clic ahí.  
- Si ya hay carpeta `.git`, no verás ese botón y puedes pasar al siguiente paso.

### 2.3 Hacer el primer commit

- En la lista de “Changes” deberían aparecer todos los archivos del proyecto.  
- Arriba del listado, en **“Message”**, escribe por ejemplo: `Initial commit - MVP invoice automation`.  
- Haz clic en el **✓ “Commit”** (o “Commit All”) para hacer el primer commit.

### 2.4 Publicar en GitHub

- Arriba verás algo como **“Publish Branch”** o **“Publish to GitHub”**.  
- Clic en **“Publish Branch”**.  
- Si te pide **iniciar sesión en GitHub**, elige “GitHub” y completa el login en el navegador.  
- Te puede preguntar si quieres crear un repo **público** o **privado** y el **nombre**. Pon el mismo nombre que creaste en la Parte 1 (ej. `invoice-automation-mvp`) y **Public**.  
- Clic en **“Publish”**.  
- Al terminar, el repo quedará en tu cuenta de GitHub.

Si en vez de “Publish” solo ves **“Sync”** o un icono de nube, antes hay que **añadir el remoto** (ver Opción B, paso 4) y luego usar “Push” o “Sync” desde ese mismo panel.

---

## Parte 3: Opción B – Desde la terminal (en Cursor o en tu Mac)

Abre la terminal en Cursor: **Terminal → New Terminal** (o **Ctrl+`** / **Cmd+`**). Asegúrate de estar en la carpeta del proyecto.

### Paso 1: Ir a la carpeta del proyecto

```bash
cd /Users/oscarguzman/invoice-automation-mvp
```

### Paso 2: Inicializar Git (si no está inicializado)

```bash
git init
```

(Si ya lo hiciste desde Cursor, dirá algo como “Reinitialized existing Git repository”.)

### Paso 3: Añadir todos los archivos y hacer el primer commit

```bash
git add .
git status
git commit -m "Initial commit - MVP invoice automation"
```

- `git status` es opcional; sirve para ver qué se va a subir.  
- Con esto ya tienes el primer commit en tu máquina.

### Paso 4: Conectar con el repo de GitHub

Sustituye `TU_USUARIO` por tu usuario de GitHub y `invoice-automation-mvp` por el nombre exacto del repo que creaste:

```bash
git remote add origin https://github.com/TU_USUARIO/invoice-automation-mvp.git
```

### Paso 5: Subir el código (primera vez)

```bash
git branch -M main
git push -u origin main
```

- Te pedirá **usuario y contraseña**. En GitHub ya no se usa contraseña normal; se usa un **Personal Access Token (PAT)**.  
  - En GitHub: **Settings → Developer settings → Personal access tokens → Generate new token**.  
  - Marca al menos **repo**.  
  - Copia el token y úsalo como “password” cuando `git push` lo pida.

Si prefieres no poner la contraseña cada vez, puedes configurar **credenciales guardadas** o **SSH** (eso lo puedes hacer después).

---

## Resumen rápido

| Dónde              | Qué hacer |
|--------------------|-----------|
| **Navegador**      | Crear cuenta GitHub → New repository (vacío) → anotar URL. |
| **Cursor (Git)**   | Initialize repo → Commit → Publish Branch (y login en GitHub si pide). |
| **Terminal**       | `git init` → `git add .` → `git commit -m "..."` → `git remote add origin URL` → `git push -u origin main`. |

La opción de **“conectar Git” y subir desde aquí** es exactamente la **Opción A** (panel de Source Control en Cursor + “Publish Branch” / “Push”). No necesitas hacerlo también por terminal si ya lo hiciste desde Cursor.

Cuando termines, en [github.com/TU_USUARIO/invoice-automation-mvp](https://github.com) deberías ver todos los archivos del proyecto.
