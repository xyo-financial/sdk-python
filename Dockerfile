# ==========================================
# Multi-stage Dockerfile for Python SDK
# ==========================================
FROM python:3.11-slim AS base
WORKDIR /app

# Install build & development dependencies
RUN pip install --no-cache-dir --upgrade pip hatchling pytest pytest-asyncio pytest-cov respx ruff mypy httpx

# Copy package metadata
COPY pyproject.toml README.md LICENSE ./

# Copy source code and test suite
COPY src/ ./src/
COPY tests/ ./tests/
COPY examples/ ./examples/

# Install package in editable mode
RUN pip install --no-cache-dir -e ".[dev]"

# Testing stage
FROM base AS test
WORKDIR /app
RUN pytest
RUN ruff check .
RUN ruff format --check .
RUN mypy src/xyo

# Build wheel package stage
FROM base AS build
WORKDIR /app
RUN pip install --no-cache-dir build && python -m build

# Default runtime image
FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=build /app/dist/*.whl ./
RUN pip install --no-cache-dir *.whl
COPY examples/ ./examples/
CMD ["python", "examples/quickstart_sync.py"]
