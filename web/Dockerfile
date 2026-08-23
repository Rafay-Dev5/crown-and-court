# Production image: builds the React client and serves it from FastAPI.
# Build from repo root:  docker build -f web/Dockerfile -t crown-court .
# Run locally:           docker run -p 8000:8000 crown-court

FROM node:20-alpine AS client-build
WORKDIR /app/web/client
COPY web/client/package.json web/client/package-lock.json ./
RUN npm ci
COPY web/client ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml web/requirements.txt ./
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir -r web/requirements.txt

COPY engine ./engine
COPY cards ./cards
COPY env ./env
COPY web ./web
COPY --from=client-build /app/web/client/dist ./web/client/dist

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')"

CMD ["sh", "-c", "uvicorn web.server.main:app --host 0.0.0.0 --port ${PORT}"]
