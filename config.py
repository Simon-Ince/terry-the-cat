"""App configuration. Railway sets DATABASE_URL when PostgreSQL is added."""
import os

# DATABASE_URL is set by Railway for the linked Postgres service.
# For local Docker Compose, it is set in docker-compose.yml.
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Optional: build from parts if you prefer (e.g. for local dev without Docker)
if not DATABASE_URL:
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "terry")
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
