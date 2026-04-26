from fastapi import FastAPI
import time
app = FastAPI()
@app.get("/items")
async def items():
    time.sleep(1)
    return {}
