# 后端镜像。基于 uv 官方镜像，装依赖后跑 uvicorn。
FROM python:3.11-slim

# uv：快速 Python 包管理
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 先只拷依赖清单，利用镜像层缓存
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev || uv pip install --system -e .

# 再拷源码
COPY . .
RUN uv sync --no-dev || true

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
