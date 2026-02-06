#!/bin/sh

# Esperar a que la base de datos esté lista
echo "Esperando a la base de datos..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Base de datos iniciada"

# Aplicar migraciones
echo "Aplicando migraciones..."
flask db upgrade

# Crear datos semilla (admin)
echo "Verificando/Creando usuario administrador..."
python seed_admin.py

# Iniciar Gunicorn
echo "Iniciando servidor..."
exec gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 app:app
