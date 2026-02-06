# Usar una imagen base oficial de Python
FROM python:3.12-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
# Se incluyen herramientas de compilación y librerías de desarrollo para Cairo/Pango
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libpq-dev \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
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
