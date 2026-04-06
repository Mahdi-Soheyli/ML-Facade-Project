FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

COPY e1300 ./e1300
COPY app ./app
COPY building_code/e1300_data ./building_code/e1300_data
COPY models ./models

# Railway sets PORT at runtime (often 8080). Do not hardcode; ${PORT:-8000} is the listen port.
ENV PORT=8000
EXPOSE 8000

# exec: signals reach uvicorn. --proxy-headers: behind Railway reverse proxy.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
