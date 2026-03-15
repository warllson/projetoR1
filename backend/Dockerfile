FROM python:3.10-slim
WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia TUDO da pasta backend (incluindo o dicionario.csv e o .db)
COPY . . 

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
