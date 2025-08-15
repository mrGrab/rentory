import io
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from uuid import uuid4
from PIL import Image
from pathlib import Path
from core.config import settings
from core.logger import logger

SUPPORTED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
router = APIRouter(prefix="/upload", tags=["Uploads"])


@router.post("/image", summary="Upload and convert image to thumbnail")
async def upload_image(image: UploadFile = File(...),
                       filename: str = Query(default=None)):
    logger.info(f"Attempting image upload: {image.filename}")
    print(filename)
    # Validate content type
    if not image.content_type.startswith("image/"):
        logger.warning("Upload rejected: Invalid image content type")
        raise HTTPException(status_code=400, detail="Invalid image format")

    ext = image.filename.split('.')[-1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        logger.warning(f"Upload rejected: Unsupported file extension: {ext}")
        raise HTTPException(status_code=400,
                            detail="Unsupported file extension")

    final_filename = f"{filename}.{ext}" if filename else f"{uuid4()}.{ext}"
    file_path = Path(settings.UPLOAD_DIR) / final_filename

    try:
        # Read and process image with Pillow
        contents = await image.read()
        original_image = Image.open(io.BytesIO(contents))
        original_image.convert("RGB")
        original_image.thumbnail((300, 300))  # Resize to thumbnail

        # Save to disk
        file_path.parent.mkdir(parents=True, exist_ok=True)
        original_image.save(file_path)
        logger.info(f"Image saved: {file_path}")
        return JSONResponse(status_code=200,
                            content={"image_url": f"{file_path}"})

    except Exception as e:
        logger.error("Image upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
