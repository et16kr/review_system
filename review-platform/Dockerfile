FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY app ./app
COPY templates ./templates

RUN uv sync --extra dev

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 18080

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "18080"]
