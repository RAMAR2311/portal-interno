FROM python:3.12-slim

WORKDIR /app

# Instalamos dependencias del sistema necesarias para compilar librerías de PDF y Postgres
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libpq-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libffi-dev \
    shared-mime-info \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Instalamos librerías de Python
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn eventlet psycopg2-binary

COPY . .

# Permisos para el script de arranque
COPY entrypoint.sh .
RUN sed -i 's/\r$//g' /app/entrypoint.sh
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:8000", "app:app"]
