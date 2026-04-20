FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY alembic ./alembic
COPY review_bot ./review_bot

RUN uv sync --frozen --extra dev

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 18081

CMD ["uvicorn", "review_bot.api.main:app", "--host", "0.0.0.0", "--port", "18081"]
