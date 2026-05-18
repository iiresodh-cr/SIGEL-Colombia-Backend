# Usar imagen oficial y ligera de Python
FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc y forzar salida estándar (útil para logs en GCP)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Crear directorio de trabajo
WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY main.py .

# Exponer el puerto por defecto de Cloud Run
EXPOSE 8080

# Iniciar el servidor FastAPI con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
