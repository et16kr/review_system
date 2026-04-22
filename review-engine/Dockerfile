FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY review_engine ./review_engine
COPY data ./data
COPY examples ./examples
COPY prompts ./prompts
COPY rules ./rules
COPY rule_sources ./rule_sources
COPY tests ./tests

RUN uv sync --frozen --extra dev

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000

CMD ["uvicorn", "review_engine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
