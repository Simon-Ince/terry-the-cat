"""App configuration. Railway sets DATABASE_URL when PostgreSQL is added."""
import os

# Connection string: check multiple env vars so we use whatever Railway provides.
# See https://dev.to/ngoakor12/connect-a-railway-databasepostgresql-with-node-postgres-in-express-15lf
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("DATABASE_PRIVATE_URL")  # Railway internal (postgres.railway.internal)
    or os.getenv("DATABASE_PUBLIC_URL")   # Railway public (containers-*.railway.app)
    or os.getenv("POSTGRES_URL")
    or os.getenv("POSTGRES_CONNECTION_STRING")
)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Railway (and most hosted Postgres) require SSL. Local Docker doesn't.
if DATABASE_URL and "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    if "sslmode" not in DATABASE_URL.lower():
        DATABASE_URL += "&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require"

# Optional: build from parts if you prefer (e.g. for local dev without Docker)
if not DATABASE_URL:
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "postgres")
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "terry")
    DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
