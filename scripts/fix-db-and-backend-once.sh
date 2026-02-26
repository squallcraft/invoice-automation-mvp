#!/bin/bash
# Ejecutar UNA SOLA VEZ en el servidor cuando backend y base quedan desincronizados
# (password authentication failed). Deja DB y backend con la misma contraseña (postgres)
# y comprueba que no vuelva a fallar.
# Uso: desde la raíz del proyecto: bash scripts/fix-db-and-backend-once.sh

set -e
cd "$(dirname "$0")/.."

echo ">>> 1. Comprobando que backend/.env NO tiene DATABASE_URL..."
if grep -q '^DATABASE_URL=' backend/.env 2>/dev/null; then
  echo "    Eliminando DATABASE_URL de backend/.env"
  sed -i '/^DATABASE_URL=/d' backend/.env
else
  echo "    OK"
fi

echo ">>> 2. Comprobando que docker-compose.yml tiene DATABASE_URL y POSTGRES_PASSWORD..."
if ! grep -q "DATABASE_URL: postgresql://postgres:postgres@db" docker-compose.yml; then
  echo "    ERROR: Añade en el servicio backend, environment:"
  echo "    DATABASE_URL: postgresql://postgres:postgres@db:5432/invoice_automation"
  exit 1
fi
if ! grep -q "POSTGRES_PASSWORD: postgres" docker-compose.yml; then
  echo "    ERROR: El servicio db debe tener POSTGRES_PASSWORD: postgres"
  exit 1
fi
echo "    OK"

echo ">>> 3. Bajando contenedores y eliminando volumen de Postgres..."
docker compose down
docker volume rm invoice-automation-mvp_pgdata 2>/dev/null || true
echo "    OK"

echo ">>> 4. Levantando todo de nuevo..."
docker compose up -d
echo "    Esperando a que db esté healthy..."
sleep 8

echo ">>> 5. Migraciones y usuario admin..."
docker compose exec -T backend flask db upgrade
docker compose exec backend python scripts/create_admin.py
echo "    OK"

echo ">>> 6. Verificación (lo que ve cada contenedor)..."
echo "    DB:     $(docker compose exec -T db env | grep POSTGRES_PASSWORD || true)"
echo "    Backend: $(docker compose exec -T backend env | grep DATABASE_URL || true)"

echo ">>> 7. Logs recientes del backend (no debe haber 'password authentication failed')..."
docker compose logs backend --tail=5

echo ""
echo ">>> Listo. Prueba la app en el navegador. No borres DATABASE_URL del compose ni pongas DATABASE_URL en backend/.env."
