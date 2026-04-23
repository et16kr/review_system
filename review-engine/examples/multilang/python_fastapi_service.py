import requests
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/items")
async def create_item(request: Request):
    payload = await request.json()
    upstream = requests.get("https://example.com/health", timeout=5)
    return {"ok": upstream.ok, "payload": payload}
