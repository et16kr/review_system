from __future__ import annotations

import re
from pathlib import Path

from review_engine.languages import get_language_registry

_BRACE_FUNC_RE = re.compile(
    r"(?:^|\n)"
    r"(?:[\w:<>*&\[\]\s]+\s+)?"
    r"([\w:~]+)\s*\([^)]{0,200}\)"
    r"\s*(?:const\s*)?\{",
    re.MULTILINE,
)
_PYTHON_BLOCK_RE = re.compile(r"(?m)^\s*(?:def|class)\s+([A-Za-z_]\w*)")
_BASH_BLOCK_RE = re.compile(r"(?m)^\s*(?:function\s+)?([A-Za-z_]\w*)\s*\(\)\s*\{")
MAX_CHUNK_CHARS = 900
MIN_CHUNK_CHARS = 40


def extract_chunks(file_path: str, content: str) -> list[dict]:
    language_id = get_language_registry().resolve(
        file_path=file_path,
        source_text=content,
    ).language_id
    if language_id in {"cpp", "c", "cuda", "typescript", "javascript", "java", "go", "rust"}:
        return _extract_structured_chunks(file_path, content, _BRACE_FUNC_RE)
    if language_id == "python":
        return _extract_structured_chunks(file_path, content, _PYTHON_BLOCK_RE)
    if language_id == "bash":
        return _extract_structured_chunks(file_path, content, _BASH_BLOCK_RE)
    return _extract_line_window_chunks(file_path, content)


def collect_reviewable_files(root: str) -> list[Path]:
    registry = get_language_registry()
    files: list[Path] = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        if registry.is_reviewable_file(str(path)):
            files.append(path)
    return files


def collect_cpp_files(root: str) -> list[Path]:
    registry = get_language_registry()
    return [
        path
        for path in collect_reviewable_files(root)
        if registry.resolve(file_path=str(path)).language_id == "cpp"
    ]


def _extract_structured_chunks(file_path: str, content: str, regex: re.Pattern[str]) -> list[dict]:
    chunks: list[dict] = []
    matches = list(regex.finditer(content))
    if not matches:
        return _extract_line_window_chunks(file_path, content)

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        snippet = content[start:end].strip()
        if len(snippet) < MIN_CHUNK_CHARS:
            continue
        if len(snippet) > MAX_CHUNK_CHARS:
            snippet = snippet[:MAX_CHUNK_CHARS]
        chunks.append(
            {
                "file_path": file_path,
                "func_name": match.group(1) or "",
                "start_line": content[:start].count("\n") + 1,
                "text": snippet,
            }
        )
    return chunks or _extract_line_window_chunks(file_path, content)


def _extract_line_window_chunks(file_path: str, content: str) -> list[dict]:
    chunks: list[dict] = []
    for i in range(0, len(content), MAX_CHUNK_CHARS):
        snippet = content[i : i + MAX_CHUNK_CHARS].strip()
        if len(snippet) < MIN_CHUNK_CHARS:
            continue
        chunks.append(
            {
                "file_path": file_path,
                "func_name": "",
                "start_line": content[:i].count("\n") + 1,
                "text": snippet,
            }
        )
    return chunks
