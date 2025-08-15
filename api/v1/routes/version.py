from fastapi import APIRouter
from fastapi.responses import JSONResponse
from core.config import settings

router = APIRouter()


@router.get(path="/version",
            summary="Get application version",
            response_description="Current version of the application")
async def read_version() -> JSONResponse:
  """
    Returns the current version of the application as defined in settings.
    """
  return JSONResponse(content={"version": settings.VERSION})
