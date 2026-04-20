from __future__ import annotations

import re
from pathlib import Path

CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
_FUNC_RE = re.compile(
    r"(?:^|\n)"                       # 줄 시작
    r"(?:[\w:<>*&\s]+\s+)?"           # 반환 타입 (선택)
    r"([\w:~]+)\s*\([^)]{0,200}\)"    # 함수명(파라미터)
    r"\s*(?:const\s*)?\{",            # {
    re.MULTILINE,
)
MAX_CHUNK_CHARS = 800
MIN_CHUNK_CHARS = 40


def extract_chunks(file_path: str, content: str) -> list[dict]:
    """C++ 파일을 함수/클래스 단위 청크로 분할한다."""
    chunks: list[dict] = []
    matches = list(_FUNC_RE.finditer(content))

    if not matches:
        # 함수 경계를 찾지 못하면 고정 크기 분할
        for i in range(0, len(content), MAX_CHUNK_CHARS):
            snippet = content[i : i + MAX_CHUNK_CHARS].strip()
            if len(snippet) >= MIN_CHUNK_CHARS:
                chunks.append(
                    {
                        "file_path": file_path,
                        "func_name": "",
                        "start_line": content[:i].count("\n") + 1,
                        "text": snippet,
                    }
                )
        return chunks

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        snippet = content[start:end].strip()
        if len(snippet) < MIN_CHUNK_CHARS:
            continue
        # 너무 긴 청크는 앞 MAX_CHUNK_CHARS 자만 사용
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
    return chunks


def collect_cpp_files(root: str) -> list[Path]:
    """디렉터리에서 C++ 파일 목록을 수집한다."""
    return [
        p
        for p in Path(root).rglob("*")
        if p.suffix in CPP_EXTENSIONS and p.is_file()
    ]
