FROM python:3.11-slim AS base

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV UVICORN_WORKERS=2
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
