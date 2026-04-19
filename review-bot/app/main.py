from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=18081)
