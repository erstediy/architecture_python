FROM python:3.11-slim

WORKDIR /app

ARG SERVICE
ARG PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ${SERVICE}/ ./${SERVICE}/

ENV SERVICE=${SERVICE}
ENV PORT=${PORT}

CMD uvicorn ${SERVICE}.main:app --host 0.0.0.0 --port ${PORT}
