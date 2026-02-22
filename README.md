# Terry the Cat

A simple app for the neighbourhood to track when Terry the cat was last fed and what he was fed.

- **Home page** – See last feeding, log a new one, and view recent feedings.
- **API** – `GET /api/feedings` (recent feedings), `GET /api/last` (most recent).

Flask + PostgreSQL. Runs on Railway or locally with Docker Compose.

## Run locally with Docker Compose

Starts the app and a local PostgreSQL database:

```bash
docker compose up --build
```

- App: http://localhost:8000  
- Health (DB status): http://localhost:8000/health  

To run in the background: `docker compose up -d --build`

Local Postgres: user `postgres`, password `postgres`, database `terry`, port `5432` (only from the app container; not exposed to the host by default).

## Railway

1. **Add PostgreSQL**: In your project, click **+ New** (or `Ctrl/Cmd + K`) and add **PostgreSQL**, or use the [PostgreSQL template](https://railway.com/template/postgres). Wait for it to deploy.
2. **Connect from your app**: In your **app service** (the one that runs this repo), [reference the PostgreSQL service’s variables](https://docs.railway.com/variables#referencing-another-services-variable) so the app receives `DATABASE_URL` (and optionally `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`). The app uses `DATABASE_URL` if set, otherwise builds a URL from the `PG*` variables. See [Railway: PostgreSQL](https://docs.railway.com/databases/postgresql).
3. **Do not** set `DATABASE_URL` to a localhost URL in the app; that will fail. Let the reference inject Railway’s URL.
4. Deploy. If something goes wrong, open **/debug** on the deployed app for connection status and hints.
