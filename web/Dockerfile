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

# Slim runtime deps only — do NOT install the full pyproject (torch/CUDA, RL stack).
COPY web/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY engine ./engine
COPY cards ./cards
COPY env ./env
COPY web ./web
COPY --from=client-build /app/web/client/dist ./web/client/dist

ENV PORT=8000
ENV PYTHONPATH=/app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8000') + '/health')"

CMD ["sh", "-c", "uvicorn web.server.main:app --host 0.0.0.0 --port ${PORT}"]
