from fastapi import APIRouter
from fastapi.responses import JSONResponse
from api.v1.routes import (
    version,
    users,
    items,
    orders,
    login,
    clients,
    upload,
    item_variants,
)

router = APIRouter(prefix="/api/v1", tags=["API v1"])
router.include_router(login.router)
router.include_router(version.router)
router.include_router(users.router)
router.include_router(items.router)
router.include_router(item_variants.router)
router.include_router(orders.router)
router.include_router(clients.router)
router.include_router(upload.router)


@router.get("/",
            summary="API v1 root endpoint",
            description="Returns a welcome message for the API v1")
async def root():
    return JSONResponse(content={"message": "Welcome to API version 1"})
