#!/bin/sh

# Esperar a que la base de datos esté lista
echo "Esperando a postgres..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL listo"

# Crear las tablas automáticamente (Versión corregida para una sola línea)
# Las tablas ahora se gestionan mediante flask-migrate (Alembic)

# Iniciar la app con Eventlet
exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app
