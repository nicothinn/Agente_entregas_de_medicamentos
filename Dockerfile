# Dockerfile multi-stage para PharmaSchedule AI
FROM python:3.11-slim as builder

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Imagen final
FROM python:3.11-slim

# Instalar dependencias del sistema para runtime
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no root
RUN useradd -m -u 1000 appuser

# Crear directorio de trabajo
WORKDIR /app

# Copiar dependencias del builder
COPY --from=builder /root/.local /home/appuser/.local

# Copiar código de la aplicación
COPY . .

# Crear directorios de datos y logs
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app

# Cambiar a usuario no root
USER appuser

# Añadir el directorio local al PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Exponer puerto de Streamlit
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8501/_stcore/health')" || exit 1

# Comando por defecto
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

