#!/usr/bin/env bash
set -euo pipefail

command -v docker >/dev/null || { echo "Docker CLI is required." >&2; exit 1; }
command -v python3 >/dev/null || { echo "Python 3 is required." >&2; exit 1; }
docker info >/dev/null
python3 -c "import docker, requests, cryptography, boto3" || {
  echo "Install node-agent/requirements.txt before running this acceptance test." >&2
  exit 1
}

suffix="$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
network="lpgp-acceptance-$suffix"
maria="lpgp-acceptance-maria-$suffix"
postgres="lpgp-acceptance-postgres-$suffix"
sftpgo="lpgp-acceptance-sftpgo-$suffix"
maria_volume="lpgp-acceptance-maria-data-$suffix"
postgres_volume="lpgp-acceptance-postgres-data-$suffix"
sftp_data_volume="lpgp-acceptance-sftp-data-$suffix"
sftp_config_volume="lpgp-acceptance-sftp-config-$suffix"
maria_root="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
maria_user="$(python3 -c 'import secrets; print("u"+secrets.token_hex(5))')"
maria_pass="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
pg_user="$(python3 -c 'import secrets; print("u"+secrets.token_hex(5))')"
pg_pass="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
sftp_admin="$(python3 -c 'import secrets; print("a"+secrets.token_hex(5))')"
sftp_admin_pass="$(python3 -c 'import secrets; print(secrets.token_urlsafe(28))')"
sftp_user="$(python3 -c 'import secrets; print("u"+secrets.token_hex(5))')"
sftp_user_pass="$(python3 -c 'import secrets; print(secrets.token_urlsafe(28))')"

cleanup() {
  docker rm -f "$maria" "$postgres" "$sftpgo" >/dev/null 2>&1 || true
  docker volume rm "$maria_volume" "$postgres_volume" "$sftp_data_volume" "$sftp_config_volume" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[1/5] Pulling the exact runtime images used by LPGP..."
docker pull mariadb:11.4
docker pull postgres:16-alpine
docker pull drakkan/sftpgo:v2.7.6
docker pull itzg/minecraft-server:java21

echo "[2/5] Creating isolated disposable Docker resources..."
docker network create "$network" >/dev/null
docker volume create "$maria_volume" >/dev/null
docker volume create "$postgres_volume" >/dev/null
docker volume create "$sftp_data_volume" >/dev/null
docker volume create "$sftp_config_volume" >/dev/null

docker run -d --name "$maria" --network "$network" -p 127.0.0.1::3306 \
  -e MARIADB_DATABASE=lpgp_test -e MARIADB_USER="$maria_user" \
  -e MARIADB_PASSWORD="$maria_pass" -e MARIADB_ROOT_PASSWORD="$maria_root" \
  -v "$maria_volume:/var/lib/mysql" mariadb:11.4 >/dev/null

docker run -d --name "$postgres" --network "$network" -p 127.0.0.1::5432 \
  -e POSTGRES_DB=lpgp_test -e POSTGRES_USER="$pg_user" -e POSTGRES_PASSWORD="$pg_pass" \
  -v "$postgres_volume:/var/lib/postgresql/data" postgres:16-alpine >/dev/null

docker run -d --name "$sftpgo" --network "$network" -p 127.0.0.1::2022 -p 127.0.0.1::8080 \
  -e SFTPGO_DEFAULT_ADMIN_USERNAME="$sftp_admin" \
  -e SFTPGO_DEFAULT_ADMIN_PASSWORD="$sftp_admin_pass" \
  -e SFTPGO_DATA_PROVIDER__CREATE_DEFAULT_ADMIN=true \
  -e SFTPGO_HTTPD__BINDINGS__0__ADDRESS=0.0.0.0 \
  -e SFTPGO_HTTPD__BINDINGS__0__PORT=8080 \
  -e SFTPGO_SFTPD__BINDINGS__0__ADDRESS=0.0.0.0 \
  -e SFTPGO_SFTPD__BINDINGS__0__PORT=2022 \
  -v "$sftp_data_volume:/srv/sftpgo/data" \
  -v "$sftp_config_volume:/var/lib/sftpgo" drakkan/sftpgo:v2.7.6 >/dev/null

maria_port="$(docker port "$maria" 3306/tcp | head -n1 | awk -F: '{print $NF}')"
postgres_port="$(docker port "$postgres" 5432/tcp | head -n1 | awk -F: '{print $NF}')"
sftp_port="$(docker port "$sftpgo" 2022/tcp | head -n1 | awk -F: '{print $NF}')"
http_port="$(docker port "$sftpgo" 8080/tcp | head -n1 | awk -F: '{print $NF}')"

echo "[3/5] Waiting for MariaDB and PostgreSQL readiness..."
for attempt in $(seq 1 90); do
  if docker exec "$maria" mariadb-admin ping -h 127.0.0.1 -uroot "-p$maria_root" --silent >/dev/null 2>&1; then
    break
  fi
  [[ "$attempt" -lt 90 ]] || { echo "MariaDB did not become ready." >&2; exit 1; }
  sleep 1
done
for attempt in $(seq 1 90); do
  if docker exec "$postgres" pg_isready -U "$pg_user" -d lpgp_test >/dev/null 2>&1; then
    break
  fi
  [[ "$attempt" -lt 90 ]] || { echo "PostgreSQL did not become ready." >&2; exit 1; }
  sleep 1
done
docker exec "$maria" mariadb -h 127.0.0.1 -u "$maria_user" "-p$maria_pass" lpgp_test -e 'SELECT 1' >/dev/null
docker exec -e PGPASSWORD="$pg_pass" "$postgres" psql -h 127.0.0.1 -U "$pg_user" -d lpgp_test -c 'SELECT 1' >/dev/null

echo "[4/5] Waiting for SFTPGo API, creating a test SFTP user, and checking its TCP listener..."
LPGP_SMOKE_HTTP_PORT="$http_port" LPGP_SMOKE_SFTP_PORT="$sftp_port" \
LPGP_SMOKE_ADMIN="$sftp_admin" LPGP_SMOKE_ADMIN_PASSWORD="$sftp_admin_pass" \
LPGP_SMOKE_USER="$sftp_user" LPGP_SMOKE_USER_PASSWORD="$sftp_user_pass" \
python3 - <<'PY'
import os, socket, time, requests
base = f"http://127.0.0.1:{os.environ['LPGP_SMOKE_HTTP_PORT']}"
for attempt in range(90):
    try:
        response = requests.get(base + "/api/v2/token",
            auth=(os.environ["LPGP_SMOKE_ADMIN"], os.environ["LPGP_SMOKE_ADMIN_PASSWORD"]),
            timeout=(2, 4))
        response.raise_for_status()
        token = response.json().get("access_token")
        if token:
            break
    except requests.RequestException:
        pass
    time.sleep(1)
else:
    raise SystemExit("SFTPGo admin API did not become ready")
response = requests.post(base + "/api/v2/users",
    headers={"Authorization": "Bearer " + token},
    json={"username": os.environ["LPGP_SMOKE_USER"],
          "password": os.environ["LPGP_SMOKE_USER_PASSWORD"],
          "home_dir": "/srv/sftpgo/data",
          "permissions": {"/": ["*"]}, "status": 1, "uid": 1000, "gid": 1000},
    timeout=(3, 10))
response.raise_for_status()
with socket.create_connection(("127.0.0.1", int(os.environ["LPGP_SMOKE_SFTP_PORT"])), timeout=5):
    pass
PY

echo "[5/5] Checking host-published database ports..."
python3 - "$maria_port" "$postgres_port" <<'PY'
import socket, sys
for port in map(int, sys.argv[1:]):
    with socket.create_connection(("127.0.0.1", port), timeout=5):
        print(f"TCP listener ready on 127.0.0.1:{port}")
PY

echo "LPGP disposable VPS acceptance checks passed. Temporary containers, volumes, and network will now be removed."
