FROM python:3.12.12-slim

WORKDIR /app

# Install system deps for Pillow and psycopg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libjpeg-dev libpng-dev libfreetype6-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
