FROM node:22-alpine AS frontend-builder
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/backend
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y exiftool libpq5 curl \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN python -m pip install --no-cache-dir .
COPY --from=frontend-builder /src/frontend/dist /app/frontend/dist
RUN python backend/manage.py collectstatic --noinput
RUN useradd --create-home --uid 10001 photochart \
    && mkdir -p /app/backend/media /app/backend/staticfiles \
    && chown -R photochart:photochart /app
USER photochart
EXPOSE 8000
CMD ["gunicorn", "--chdir", "backend", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-", "backend.wsgi:application"]

FROM nginx:1.27-alpine AS gateway
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /src/frontend/dist /usr/share/nginx/html
EXPOSE 8080
