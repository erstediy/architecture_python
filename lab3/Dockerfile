FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ARG SERVICE=auth_service
ARG PORT=8000
ENV SERVICE=${SERVICE}
ENV PORT=${PORT}
CMD uvicorn ${SERVICE}.main:app --host 0.0.0.0 --port ${PORT}
EXPOSE ${PORT}
