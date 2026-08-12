"""GameDevCopilot web demo — run with:

    python -m web.app
"""
from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="GameDevCopilot", description="一句话生成游戏原型")
app.include_router(router)
app.mount("/static", StaticFiles(directory="web/static"), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
