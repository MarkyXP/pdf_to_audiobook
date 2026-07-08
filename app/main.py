import logging
from contextlib import asynccontextmanager

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import settings
from app.api.routes import router as api_router
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories exist
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.voice_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown: clean up


def create_app() -> FastAPI:
    app = FastAPI(
        title="ebooks",
        description="PDF-to-audio backend with pocket_tts",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api")
    app.include_router(web_router)
    return app


app = create_app()
