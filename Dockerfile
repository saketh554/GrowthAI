FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
COPY data ./data
COPY eval ./eval
COPY docs ./docs
COPY PROGRESS.md ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN uv sync --frozen

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
