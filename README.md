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

1. Add a **PostgreSQL** plugin to your project (New → Database → PostgreSQL).
2. In your **app service** (the one that runs this repo), link the PostgreSQL service so Railway injects `DATABASE_URL` (e.g. Settings → Connect, or add a variable reference to the database).
3. Use the connection URL Railway provides. It may use the host **`postgres.railway.internal`** (Railway’s private network) – that’s correct. Your app reads `DATABASE_URL`; no code changes needed. **Do not** overwrite it with a localhost URL.
4. If Railway exposes both a public URL and a private one (e.g. `DATABASE_PUBLIC_URL` vs `DATABASE_PRIVATE_URL`), reference the **private** variable as `DATABASE_URL` so the app uses `postgres.railway.internal` and stays on the internal network.
5. Deploy. If something goes wrong, open **/debug** on the deployed app for connection status and hints.
