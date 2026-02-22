FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py config.py .

# Default port (overridable via PORT env)
ENV PORT=8000
EXPOSE 8000

# Match Railway: gunicorn main:app (PORT is overridable via env)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} main:app"]
