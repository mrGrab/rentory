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
from core.database import create_db_and_tables
from api.main import router as api_router

log_level = settings.LOG_LEVEL.lower()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for setting up resources before app startup."""

    logger.setLevel(LOG_LEVELS[log_level])
    try:
        create_db_and_tables()
    except Exception as e:
        print("PRE starting error: ", e)
        raise
    yield


# Initialize FastAPI app
app = FastAPI(title="Rentory",
              version=settings.VERSION,
              openapi_url="/api/openapi.json",
              docs_url="/docs",
              redoc_url="/redoc",
              lifespan=lifespan,
              description="""
## API Versions
- **v1**: Current stable version
""")

# Add middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)
app.add_middleware(CORSMiddleware,
                   allow_origins=settings.BACKEND_CORS_ORIGINS,
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"],
                   expose_headers=["Content-Range"])


# Routes
@app.get('/robots.txt', response_class=PlainTextResponse)
def robots():
    """Returns a simple robots.txt file."""
    return """User-agent: *\nDisallow: /"""


# Include API router
app.include_router(api_router)

# Static files
app.mount(f"/{settings.UPLOAD_DIR}",
          StaticFiles(directory=settings.UPLOAD_DIR),
          name="static")
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True))

# Run Uvicorn server
if __name__ == '__main__':
    uvicorn.run(app="main:app",
                host=settings.APP_HOST,
                port=settings.APP_PORT,
                log_config=LOGGING_CONFIG,
                log_level=log_level,
                reload=settings.APP_RELOAD)
