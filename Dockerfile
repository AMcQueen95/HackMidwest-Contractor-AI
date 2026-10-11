# Build the browser bundle without passing any server credentials to Vite.
FROM node:24-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt
COPY --chown=10001:10001 backend/ ./backend/
COPY --chown=10001:10001 --from=frontend-build /app/frontend/dist ./frontend/dist/
RUN useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
# Render supplies PORT and terminates HTTPS at its ingress. Trust forwarded
# headers there so the application sees the public HTTPS scheme. One worker
# keeps the current temporary AI conversation/cache behavior consistent.
CMD ["sh", "-c", "exec python -m uvicorn backend.app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
