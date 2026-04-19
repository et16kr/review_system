FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md review_system.md CODING_CONVENTION.md ./
COPY app ./app
COPY data ./data
COPY examples ./examples
COPY tests ./tests

RUN uv sync --frozen --extra dev

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
