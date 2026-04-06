FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

COPY e1300 ./e1300
COPY app ./app
COPY building_code/e1300_data ./building_code/e1300_data
COPY models ./models

# Railway sets PORT at runtime (commonly 8080). Image default matches Railway so local Docker matches deploy.
ENV PORT=8080
EXPOSE 8080

# exec: signals reach uvicorn. --proxy-headers: behind Railway reverse proxy.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
