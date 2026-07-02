FROM python:3.11-slim

WORKDIR /app

# System dependencies:
#   libmagic1  - python-magic (uploads)
#   openssl    - RSA keypair generation for JWT (VULN-21/22)
#   netcat     - simple wait-for-DB in entrypoint.sh
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    openssl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads /app/keys \
    && chmod +x /app/entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:create_app()"]
