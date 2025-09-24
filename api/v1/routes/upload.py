import io
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, status
from PIL import Image, ImageOps

# --- Project Imports ---
from core.config import settings
from core.logger import logger
from core.dependencies import CurrentUser
from core.exceptions import BadRequestException, InternalErrorException

# --- Configuration ---
# Keep settings centralized for clarity
SUPPORTED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
THUMBNAIL_SIZE = (300, 300)
DEFAULT_JPEG_QUALITY = 85

router = APIRouter(prefix="/upload", tags=["Uploads"])


def create_thumbnail(image_data: bytes, output_path: Path) -> dict:
    """
    Opens image data, creates a thumbnail, and saves it as an optimized JPEG.

    This function handles image orientation, converts various modes (like PNGs with
    transparency) to RGB by placing them on a white background, and saves an
    optimized thumbnail.
    """
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            original_size = img.size

            # Correct orientation based on EXIF
            img = ImageOps.exif_transpose(img)

            # Convert to RGB, handling transparency by pasting on a white background
            if img.mode != 'RGB':
                background = Image.new('RGB', img.size, "white")
                # Paste the image using its alpha channel as a mask if it exists
                if 'A' in img.getbands():
                    background.paste(img, mask=img.getchannel('A'))
                else:
                    background.paste(img)
                img = background

            # Create a high-quality thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Ensure the target directory exists before saving
            output_path.parent.mkdir(parents=True, exist_ok=True)

            img.save(output_path,
                     format="JPEG",
                     quality=DEFAULT_JPEG_QUALITY,
                     optimize=True,
                     progressive=True)

            return {
                "original_size": {
                    "width": original_size[0],
                    "height": original_size[1]
                },
                "thumbnail_size": {
                    "width": img.width,
                    "height": img.height
                },
                "file_size": output_path.stat().st_size,
            }
    except Exception as e:
        logger.error(f"Thumbnail creation failed unexpectedly: {e}")
        raise InternalErrorException(
            "An unexpected error occurred while processing the image.")


@router.post(
    "/image",
    summary="Upload and process an image",
    description="Upload an image, which will be converted to a JPEG thumbnail.",
    status_code=status.HTTP_201_CREATED)
async def upload_image(current_user: CurrentUser,
                       image: UploadFile = File(...)):
    """
    Handles the image upload process:
    1. Validates the file type and size.
    2. Generates a secure, unique filename.
    3. Processes the image into a thumbnail.
    4. Returns the URL and processing details.
    """
    logger.info(f"User '{current_user.username}' uploading: {image.filename}")

    # --- 1. Validation ---
    if not image.content_type or not image.content_type.startswith("image/"):
        raise BadRequestException("File must be an image.")

    file_ext = Path(image.filename).suffix.lower().lstrip('.')
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise BadRequestException(f"Unsupported image type: '{file_ext}'.")

    image_data = await image.read()
    if len(image_data) > MAX_FILE_SIZE_BYTES:
        raise BadRequestException(
            f"File is too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")

    # --- 2. Processing & Saving ---
    # Generate a secure, unique filename. We always save as .jpg.
    new_filename = f"{uuid4()}.jpg"
    output_path = Path(settings.UPLOAD_DIR) / new_filename

    processing_info = create_thumbnail(image_data, output_path)

    logger.info(
        f"Image uploaded successfully to {output_path} by '{current_user.username}'"
    )

    return {
        "message": "Image uploaded successfully.",
        "image_url": f"/static/images/{new_filename}",
        "details": processing_info
    }
