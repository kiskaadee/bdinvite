# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev
COPY backend/ .
COPY --from=frontend-build /build/dist ./static
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
