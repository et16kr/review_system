from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from review_engine.codebase.indexer import collect_cpp_files, extract_chunks
from review_engine.codebase.store import CodebaseStore
from review_engine.config import get_settings
from review_engine.models import ReviewCodeRequest, ReviewDiffRequest
from review_engine.retrieve.search import GuidelineSearchService

app = FastAPI(title="Review System", version="0.2.0")
service = GuidelineSearchService()
_codebase_store = CodebaseStore(get_settings())


class CodebaseIndexRequest(BaseModel):
    root_path: str
    clear_first: bool = False


class CodebaseSearchRequest(BaseModel):
    query: str
    top_k: int = 3


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(force_refresh: bool = False):
    return service.ingest(force_refresh=force_refresh).model_dump()


@app.post("/review/code")
def review_code(request: ReviewCodeRequest):
    return service.review_code(request.code, top_k=request.top_k).model_dump()


@app.post("/review/diff")
def review_diff(request: ReviewDiffRequest):
    return service.review_diff(
        request.diff,
        top_k=request.top_k,
        file_context=request.file_context,
    ).model_dump()


@app.get("/rule/{rule_no}")
def get_rule(rule_no: str):
    rule = service.inspect_rule(rule_no)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_no}")
    return rule.model_dump()


@app.post("/codebase/index")
def index_codebase(request: CodebaseIndexRequest):
    root_path = _resolve_codebase_root(request.root_path)
    if request.clear_first:
        _codebase_store.clear()
    files = collect_cpp_files(str(root_path))
    total_chunks = 0
    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            chunks = extract_chunks(str(path), content)
            total_chunks += _codebase_store.upsert_chunks(chunks)
        except Exception:
            continue
    return {"indexed_files": len(files), "total_chunks": total_chunks}


@app.post("/codebase/search")
def search_codebase(request: CodebaseSearchRequest):
    results = _codebase_store.search(request.query, top_k=request.top_k)
    return {"results": results}


def _resolve_codebase_root(root_path: str) -> Path:
    try:
        resolved = Path(root_path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"root_path not found: {root_path}") from exc

    if not resolved.is_dir():
        raise HTTPException(status_code=400, detail=f"root_path must be a directory: {root_path}")

    allowed_roots = _allowed_codebase_roots()
    if not any(resolved == allowed_root or allowed_root in resolved.parents for allowed_root in allowed_roots):
        allowed_text = ", ".join(str(item) for item in allowed_roots)
        raise HTTPException(
            status_code=403,
            detail=f"root_path must stay within allowed roots: {allowed_text}",
        )
    return resolved


def _allowed_codebase_roots() -> tuple[Path, ...]:
    configured = os.getenv("REVIEW_ENGINE_CODEBASE_ALLOWED_ROOTS")
    if configured:
        roots = [
            Path(item).expanduser().resolve()
            for item in configured.split(os.pathsep)
            if item.strip()
        ]
    else:
        roots = [get_settings().project_root.parent.resolve()]
    return tuple(roots)
