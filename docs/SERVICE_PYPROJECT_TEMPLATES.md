# 서비스별 `pyproject.toml` 초안

## 1. 목적

이 문서는 workspace 분리 후 각 서비스에 둘 `pyproject.toml`의 기준 초안을 정의한다.
실제 생성 시에는 이 문서를 그대로 복사해 시작한다.

## 2. `review-engine`

역할:

- 규칙 파싱
- vector DB ingest
- 코드/`diff` 리뷰 검색 API

```toml
[project]
name = "review-engine"
version = "0.1.0"
description = "Altibase-first C++ guideline review engine."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "beautifulsoup4>=4.12.3",
  "chromadb>=0.5.5",
  "fastapi>=0.115.0",
  "httpx>=0.27.2",
  "numpy>=2.1.1",
  "pydantic>=2.9.2",
  "uvicorn>=0.31.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "ruff>=0.6.9",
]

[project.scripts]
ingest-guidelines = "app.cli.ingest_guidelines:main"
review-cpp-code = "app.cli.review_cpp_code:main"
review-cpp-diff = "app.cli.review_cpp_diff:main"
inspect-rule = "app.cli.inspect_rule:main"
evaluate-examples = "app.cli.evaluate_examples:main"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]

[tool.setuptools.package-data]
app = ["py.typed"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

## 3. `review-platform`

역할:

- Git 저장소/PR/댓글/웹 UI

```toml
[project]
name = "review-platform"
version = "0.1.0"
description = "Internal Git PR review platform."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.31.0",
  "jinja2>=3.1.4",
  "sqlalchemy>=2.0.35",
  "alembic>=1.13.3",
  "psycopg[binary]>=3.2.3",
  "pydantic>=2.9.2",
  "python-multipart>=0.0.12",
  "itsdangerous>=2.2.0",
  "passlib[bcrypt]>=1.7.4",
  "httpx>=0.27.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-asyncio>=0.24.0",
  "ruff>=0.6.9",
]

[project.scripts]
platform-api = "app.main:main"
platform-migrate = "app.db.migrate:main"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]

[tool.setuptools.package-data]
app = ["py.typed", "templates/**/*.html", "static/**/*"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

## 4. `review-bot`

역할:

- PR 이벤트 수신
- 엔진 호출
- LLM 호출
- finding dedupe
- top 5 게시

```toml
[project]
name = "review-bot"
version = "0.1.0"
description = "Automated PR review bot for internal Git review platform."
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.31.0",
  "httpx>=0.27.2",
  "pydantic>=2.9.2",
  "sqlalchemy>=2.0.35",
  "psycopg[binary]>=3.2.3",
  "redis>=5.1.1",
  "rq>=1.16.2",
  "openai>=1.51.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-asyncio>=0.24.0",
  "ruff>=0.6.9",
]

[project.scripts]
bot-api = "app.main:main"
bot-worker = "app.jobs.worker:main"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["app"]

[tool.setuptools.package-data]
app = ["py.typed"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

## 5. 공통 규칙

세 서비스 모두 아래를 지킨다.

- Python 3.11+
- FastAPI 기반
- `ruff`
- `pytest`
- `pydantic`
- ASCII 우선
- 패키지명은 서비스 폴더와 동일

## 6. 초기 생성 순서

1. `review-engine/pyproject.toml`
2. `review-platform/pyproject.toml`
3. `review-bot/pyproject.toml`

처음에는 루트 pyproject를 지우지 않는다. workspace 전환이 완료된 뒤 정리한다.
