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

On Railway, add the PostgreSQL plugin and link it to your service. Railway sets `DATABASE_URL` automatically; no extra config needed.
