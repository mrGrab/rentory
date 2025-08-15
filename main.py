#!/usr/bin/env python3
# coding: UTF-8

import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.logger import logger, LOG_LEVELS, LOGGING_CONFIG
from core.dependency import create_db_and_tables
from api.main import router as api_v1_router

log_level = settings.LOG_LEVEL.lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for setting up resources before app startup."""

    logger.setLevel(LOG_LEVELS[log_level])
    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        create_db_and_tables()
    except Exception as e:
        print("PRE starting error: ", e)
        raise
    yield


# Initialize FastAPI app
app = FastAPI(title="Rentory",
              version=settings.VERSION,
              openapi_url=f"/api/openapi.json",
              docs_url="/docs",
              redoc_url="/redoc",
              lifespan=lifespan,
              description="""
## API Versions
- **v1**: Current stable version
""")

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5233", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range"],
)


@app.get('/robots.txt', response_class=PlainTextResponse)
def robots():
    """Returns a simple robots.txt file."""
    return """User-agent: *\nDisallow: /"""


# Register routers
app.include_router(api_v1_router)
app.mount(f"/{settings.UPLOAD_DIR}",
          StaticFiles(directory=settings.UPLOAD_DIR),
          name="static")
app.mount("/", StaticFiles(directory="frontend/dist", html=True))

# Run Uvicorn server
if __name__ == '__main__':
    uvicorn.run(app="main:app",
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                log_config=LOGGING_CONFIG,
                log_level=log_level,
                reload=settings.APP_RELOAD)
