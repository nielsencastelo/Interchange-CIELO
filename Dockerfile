FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema para pdfplumber / pypdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código-fonte
COPY . .

# Porta padrão (API = 8000, Dashboard = 8501)
EXPOSE 8000 8501

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
