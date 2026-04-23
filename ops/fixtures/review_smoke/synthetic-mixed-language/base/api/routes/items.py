import httpx
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/items")
async def create_item(request: Request):
    payload = await request.json()
    async with httpx.AsyncClient(timeout=5) as client:
        upstream = await client.get("https://example.com/health")
    return {"ok": upstream.is_success, "payload": payload}
