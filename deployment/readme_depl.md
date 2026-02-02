# Deployment Script Overview (Ubuntu 24.04)

This document explains what `deployment/deploy_web_server.sh` does and which inputs it expects.

## What the script does

1. **Clones or updates the repository**
   - Clones the repo into `deployment/Adamant_full` by default.
   - If the repo already exists, it pulls the selected branch (unless `--no-pull` or `--no-update` is passed).

2. **Optional cleanup**
   - If you pass `--clean`/`--cleanup`, it removes existing Node.js/npm installs and old `node_modules` + lockfiles to avoid conflicts.

3. **Installs system dependencies**
   - Installs Node.js (via NodeSource), Python build tools, MariaDB, Nginx, Certbot, and `apache2-utils` (for Basic Auth).

4. **Loads environment configuration**
   - Reads `.env` from `deployment/.env` or from the repo root.
   - Requires `BASIC_AUTH_USER` and `BASIC_AUTH_PASSWORD` to be set.

5. **Configures MariaDB**
   - Creates the database and user from `.env`.
   - Writes `backend/conf/db_config.json` for the backend.

6. **Sets up Python backend**
   - Creates a virtual environment in `backend/venv`.
   - Installs backend requirements and WebDAV ingester requirements.
   - Creates and enables a systemd service for:
     - `adamant-backend` (Gunicorn on port 5000)
     - `adamant-webdav-ingest` (continuous WebDAV polling)

7. **Builds the frontend and DB UI**
   - Runs `npm install` and `npm run build` in the root app and `db-ui/`.
   - Copies build output to `/var/www/html/build` and `/var/www/html/build/db-ui`.

8. **Configures Nginx + Basic Auth**
   - Writes the Nginx config directly from the script.
   - Enables Basic Auth with the realm from `.env`.
   - Writes `/etc/nginx/.htpasswd` using the provided credentials.

9. **Optional SSL via Certbot**
   - If `SSL_DOMAIN` is set, it requests a cert with Certbot and reloads Nginx.

## Required environment variables

Create a `.env` based on `env.example`. At minimum, set:

- `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD`
- `SSL_EMAIL`, `SSL_DOMAIN` (if you want HTTPS)
- `WEBDAV_URL`, `WEBDAV_USER`, `WEBDAV_PASSWORD`, `WEBDAV_ROOT`

## WebDAV ingest explained

The WebDAV ingester (`bin/webdav_ingest.py`) runs as a systemd service (`adamant-webdav-ingest`) and continuously polls a remote WebDAV folder for JSON files. The flow is:

1. **Connect to WebDAV**
   - Uses `WEBDAV_URL` as the base endpoint (e.g., `https://<host>/remote.php/dav/files/<user>/`).
   - Appends `WEBDAV_ROOT` to build the target folder.

2. **Discover files**
   - Issues a `PROPFIND` request to list entries.
   - Filters for `.json` files.

3. **Validate and insert**
   - Downloads each JSON file.
   - Checks `FileTypeIdentifier` and `SchemaID`.
   - Loads the matching schema from `SCHEMA_DIR`.
   - Validates the JSON, then inserts into the matching MariaDB table.

4. **State tracking**
   - Uses a MariaDB table `ingest_state` to store ETag/last-modified info.
   - Skips unchanged files, logs errors and skips.

### WebDAV settings (from `.env`)

- `WEBDAV_URL`  
  Base WebDAV endpoint (must end with `/` or it will be normalized).

- `WEBDAV_ROOT`  
  Folder under the base URL that contains the JSON files.

- `WEBDAV_USER` / `WEBDAV_PASSWORD`  
  Credentials used for Basic Auth on the WebDAV server.

- `SCHEMA_DIR`  
  Local directory containing schema JSON files (default `./backend/schemas`).

- `POLL_INTERVAL`  
  Polling interval in seconds.

- `ALLOWED_SCHEMAIDS`  
  Optional comma-separated allow-list for SchemaIDs.

## Usage

```bash
cd deployment
./deploy_web_server.sh
```

Optional flags:

- `--no-pull` / `--no-update` → do not update an existing repo
- `--clean` / `--cleanup` → remove old Node.js/npm + `node_modules`

## Services installed

- `adamant-backend`  
  Gunicorn running the Flask API on port `5000`.

- `adamant-webdav-ingest`  
  WebDAV polling and ingestion into MariaDB.

Use `systemctl status <service>` to verify their state.

## How to verify services

### Check service status

```bash
systemctl status adamant-backend
systemctl status adamant-webdav-ingest
```

### Check service logs

```bash
journalctl -u adamant-backend -n 200 --no-pager
journalctl -u adamant-webdav-ingest -n 200 --no-pager
```

### Check API health

```bash
curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASSWORD" http://localhost/api/check_mode
```

### Check Nginx auth

```bash
curl -I http://localhost
curl -u "$BASIC_AUTH_USER:$BASIC_AUTH_PASSWORD" -I http://localhost
```
