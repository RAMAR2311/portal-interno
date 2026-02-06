# Usar una imagen base oficial de Python
FROM python:3.12-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
# - build-essential y libpq-dev para compilar/conectar PostgreSQL
# - librerías para reportlab y procesamiento de imágenes (cairo, pango)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    gdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copiar el archivo de requerimientos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código de la aplicación
COPY . .

# Dar permisos de ejecución al script de entrada y corregir finales de línea (CRLF a LF)
COPY entrypoint.sh .
RUN sed -i 's/\r$//g' /app/entrypoint.sh
RUN chmod +x entrypoint.sh

# Exponer el puerto
EXPOSE 8000

# Usar el script de entrada para arrancar
ENTRYPOINT ["./entrypoint.sh"]
