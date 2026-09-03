FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.18 /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    # Streamlit puts the script's own directory on sys.path, not the project root,
    # so `import src...` needs /app declared explicitly.
    PYTHONPATH=/app

# Dependency layer, cached independently of the source below.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src/ ./src/

EXPOSE 8501

CMD ["uv", "run", "--no-sync", "streamlit", "run", "src/app/main.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
