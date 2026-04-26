from fastapi import FastAPI, Request
app = FastAPI()
@app.post("/items")
async def items(request: Request):
    payload = await request.body()
    return payload
