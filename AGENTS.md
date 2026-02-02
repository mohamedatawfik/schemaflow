# AGENTS.md

## Purpose
- Adamant is a JSON-Schema-based metadata editor and data intake tool for research workflows (FAIR-style metadata).
- The UI renders interactive forms from JSON Schema, validates input, and produces JSON datasets that can be ingested into MariaDB.

## High-level architecture
- Frontend (Vite + React) in `src/`
  - Loads schemas from the backend (`/api/get_schemas`) or uses bundled examples in `src/schemas`.
  - Supports schema upload, schema creation from scratch, editing, and drag/drop ordering of fields.
  - Create-from-scratch uses JSON Schema draft-07 and injects a required `FileTypeIdentifier` plus core fields (Identifier, Creator, ORCID, Date, Time, Project).
  - Validates form data with AJV (draft-04 + latest) and shows structured error messages.
  - Can upload a JSON dataset to pre-fill the form (drag/drop in the renderer uses `fillForm`).
  - Downloads JSON schema and JSON dataset; dataset download injects `SchemaID` derived from the selected schema file name.
  - "Browse experiments" embeds the DB UI; dev uses `http://localhost:3001/db-ui/`, prod uses `/db-ui/`.
- Backend (Flask) in `backend/api.py`
  - Reads DB config from `backend/conf/db_config.json`.
  - Endpoints: `/api/check_mode`, `/api/get_schemas`, `/api/save_schema`, `/api/tables`, `/api/data/<table>`, `/api/columns/<table>`, `/api/left-join`.
  - `/api/check_mode` reads `backend/conf/jobrequest-conf.json` (if present) to drive job request workflows.
  - `save_schema` injects a `SchemaID` property (enum = `$id`), writes schema to `backend/schemas/`, and (re)creates the matching DB table.
  - Table creation flattens object properties, maps JSON types to SQL, appends `documentlocation`, and drops the table before recreate (destructive).
- DB UI (Vite + React) in `db-ui/`
  - DataGrid page: lists tables, columns, rows; filters; hides FileTypeIdentifier/SchemaID/documentlocation by default; CSV/XLSX export.
  - Join page: uses `/api/left-join` to merge two tables and export results.

## Data ingestion (WebDAV)
- `bin/webdav_ingest.py`
  - Polls a WebDAV folder, downloads JSON files, validates against local schemas, and upserts into MariaDB.
  - Uses `.env` (or CLI flags) for WebDAV credentials, polling interval, and schema directory.

## Configuration
- `.env` (see `env.example`) controls DB credentials, WebDAV settings, schema directory, and SSL settings.
- `backend/conf/db_config.json` is the runtime DB config (overwritten by deployment script).

## Development
- Frontend: `npm install` then `npm run dev` (root).
- Backend: `cd backend`, create venv, `pip install -r requirements.txt`, run `gunicorn -b :5000 api:app` or `flask run`.
- DB UI: `cd db-ui`, `npm install`, `npm run dev`.

## Deployment (Ubuntu 24.04)
- `deployment/deploy_web_server.sh`
  - Installs Node/Python/MariaDB/Nginx, builds frontend + db-ui to `/var/www/html/build`, and configures systemd for backend.
