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

1. **Add PostgreSQL**: In your project, choose “Provision PostgreSQL” (or New → Database → PostgreSQL) and wait for it to finish.
2. **Get the connection URL**: Open the **PostgreSQL** service → **Connect** tab. Copy the **“Postgres Connection URL”** (it looks like `postgresql://postgres:...@containers-us-west-XX.railway.app:PORT/railway` or uses `postgres.railway.internal`). See [Connect a Railway database (PostgreSQL) with Express](https://dev.to/ngoakor12/connect-a-railway-databasepostgresql-with-node-postgres-in-express-15lf) for the same flow.
3. **Set it in your app**: In your **app service** (the one that runs this repo) → **Variables**, add **`DATABASE_URL`** and paste that URL. (If you link the database instead, Railway may inject `DATABASE_URL`, `DATABASE_PRIVATE_URL`, or `DATABASE_PUBLIC_URL`; the app uses whichever is set.)
4. **Do not** set `DATABASE_URL` to a localhost URL; that will fail on Railway.
5. Deploy. If something goes wrong, open **/debug** on the deployed app for connection status and hints.
