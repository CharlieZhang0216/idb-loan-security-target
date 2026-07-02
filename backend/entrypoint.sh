#!/bin/sh
# entrypoint.sh - wait for the DB, generate JWT keypair, seed demo hashes,
# then hand off to the CMD (gunicorn).
set -e

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
KEYS_DIR="${JWT_KEYS_DIR:-/app/keys}"

echo "[entrypoint] waiting for postgres at ${DB_HOST}:${DB_PORT}..."
for i in $(seq 1 60); do
  if nc -z "${DB_HOST}" "${DB_PORT}" 2>/dev/null; then
    echo "[entrypoint] postgres is up"
    break
  fi
  sleep 1
done

# Generate an RSA keypair used by VULN-21/VULN-22 (JWKS + kid path traversal).
mkdir -p "${KEYS_DIR}"
if [ ! -f "${KEYS_DIR}/jwt_priv.pem" ]; then
  echo "[entrypoint] generating JWT RSA keypair in ${KEYS_DIR}"
  openssl genrsa -out "${KEYS_DIR}/jwt_priv.pem" 2048 >/dev/null 2>&1 || true
  openssl rsa -in "${KEYS_DIR}/jwt_priv.pem" -pubout -out "${KEYS_DIR}/jwt_pub.pem" >/dev/null 2>&1 || true
fi

# Seed demo password hashes now that Postgres is reachable. Failure is
# non-fatal so the container still starts (the app can log in with the
# static hashes from init.sql).
python3 seeds/hash_passwords.py || echo "[entrypoint] password seeding skipped"

echo "[entrypoint] launching: $*"
exec "$@"
