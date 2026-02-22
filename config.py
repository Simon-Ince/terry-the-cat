"""App configuration. Railway: connect by referencing the PostgreSQL service variables."""
import os
from urllib.parse import quote_plus

# Session and CSRF; set SECRET_KEY in production (e.g. Railway variables)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

# Railway exposes these when you reference the PostgreSQL service:
# PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE, DATABASE_URL
# https://docs.railway.com/databases/postgresql
DATABASE_URL = os.getenv("DATABASE_URL")

# If no DATABASE_URL, build from Railway's PG* vars or local fallbacks
if not DATABASE_URL:
    host = os.getenv("PGHOST") or os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("PGPORT") or os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("PGUSER") or os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB", "terry")
    # Quote password in case it contains special characters
    password_quoted = quote_plus(password)
    DATABASE_URL = f"postgresql://{user}:{password_quoted}@{host}:{port}/{dbname}"

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Railway Postgres is SSL-enabled; local Docker isn't
if DATABASE_URL and "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    if "sslmode" not in DATABASE_URL.lower():
        DATABASE_URL += "&sslmode=require" if "?" in DATABASE_URL else "?sslmode=require"
