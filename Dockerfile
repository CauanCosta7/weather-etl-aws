FROM python:3.12-slim

WORKDIR /app

# Instalar dependências do sistema para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY config.py extract.py transform.py load.py pipeline.py ./

CMD ["python", "pipeline.py"]
