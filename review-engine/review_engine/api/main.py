from __future__ import annotations

from fastapi import FastAPI, HTTPException

from review_engine.models import ReviewCodeRequest, ReviewDiffRequest
from review_engine.retrieve.search import GuidelineSearchService

app = FastAPI(title="Review System", version="0.1.0")
service = GuidelineSearchService()


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
    return service.review_diff(request.diff, top_k=request.top_k).model_dump()


@app.get("/rule/{rule_no}")
def get_rule(rule_no: str):
    rule = service.inspect_rule(rule_no)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_no}")
    return rule.model_dump()
