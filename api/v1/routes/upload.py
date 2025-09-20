import io
from pathlib import Path
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, status
from PIL import Image, ImageOps

from core.config import settings
from core.logger import logger
from core.dependencies import CurrentUser

# Configuration
SUPPORTED_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff"
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
THUMBNAIL_SIZE = (300, 300)
DEFAULT_QUALITY = 85

router = APIRouter(prefix="/upload", tags=["Uploads"])


def validate_image_file(file: UploadFile) -> str:
    """Validate uploaded image file and return file extension"""

    # Check content type
    if not file.content_type or not file.content_type.startswith("image/"):
        logger.warning(f"Invalid content type: {file.content_type}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="File must be an image")

    # Extract and validate file extension
    if not file.filename or '.' not in file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Filename must have an extension")

    extension = file.filename.split('.')[-1].lower()
    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        logger.warning(f"Unsupported extension: {extension}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=
            f"Unsupported file type. Supported: {', '.join(SUPPORTED_IMAGE_EXTENSIONS)}"
        )

    return extension


def generate_filename(custom_filename: Optional[str], extension: str) -> str:
    """Generate a safe filename for the uploaded image"""
    if custom_filename:
        # Sanitize custom filename
        safe_filename = "".join(
            c for c in custom_filename if c.isalnum() or c in ".-_")
        if not safe_filename:
            safe_filename = str(uuid4())
        return f"{safe_filename}.{extension}"
    else:
        return f"{uuid4()}.{extension}"


def process_image(image_data: bytes,
                  output_path: Path,
                  thumbnail_size: tuple = THUMBNAIL_SIZE) -> dict:
    """Process image: resize, optimize, and save"""
    try:
        # Open and process image
        with Image.open(io.BytesIO(image_data)) as img:
            # Get original dimensions
            original_width, original_height = img.size

            # Handle EXIF orientation
            img = ImageOps.exif_transpose(img)

            # Convert to RGB if necessary (handles RGBA, P mode images)
            if img.mode in ("RGBA", "P"):
                # Create white background for transparency
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(
                    img, mask=img.split()[-1])  # Use alpha channel as mask
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Create thumbnail while maintaining aspect ratio
            img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)

            # Ensure upload directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Save with optimization
            img.save(output_path,
                     format="JPEG",
                     quality=DEFAULT_QUALITY,
                     optimize=True,
                     progressive=True)

            return {
                "original_size": {
                    "width": original_width,
                    "height": original_height
                },
                "thumbnail_size": {
                    "width": img.width,
                    "height": img.height
                },
                "file_size": output_path.stat().st_size
            }

    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to process image")


@router.post(
    "/image",
    summary="Upload and process image",
    description="Upload an image file, convert to thumbnail, and save to server"
)
async def upload_image(
    current_user: CurrentUser,
    image: UploadFile = File(..., description="Image file to upload"),
    filename: Optional[str] = Query(None,
                                    description="Custom filename (optional)")):
    """Upload and process an image file"""

    logger.info(
        f"User {current_user.username} uploading image: {image.filename}")

    # Validate file
    extension = validate_image_file(image)

    # Check file size
    if hasattr(image, 'size') and image.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=
            f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Generate filename and path
    final_filename = generate_filename(filename, extension)
    file_path = Path(settings.UPLOAD_DIR) / final_filename

    # Check if file already exists
    if file_path.exists():
        logger.warning(f"File already exists: {final_filename}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="File with this name already exists")

    try:
        # Read file data
        image_data = await image.read()

        # Validate file size after reading
        if len(image_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=
                f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Process and save image
        processing_info = process_image(image_data, file_path)

        # Generate URL (assuming you have a static file serving setup)
        image_url = f"/{settings.UPLOAD_DIR}/{final_filename}"

        logger.info(
            f"Image uploaded successfully: {file_path} by {current_user.username}"
        )

        return {
            "message": "Image uploaded successfully",
            "filename": final_filename,
            "image_url": image_url,
            "processing_info": processing_info
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        # Clean up file if it was created but processing failed
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to cleanup file {file_path}: {cleanup_error}")

        logger.error(f"Image upload failed for {current_user.username}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Image upload failed")


@router.delete("/image/{filename}",
               summary="Delete uploaded image",
               description="Delete an uploaded image file")
async def delete_image(current_user: CurrentUser, filename: str):
    """Delete an uploaded image file"""

    logger.info(f"User {current_user.username} deleting image: {filename}")

    # Validate filename
    if not filename or '..' in filename or '/' in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid filename")

    file_path = Path(settings.UPLOAD_DIR) / filename

    # Check if file exists
    if not file_path.exists():
        logger.warning(f"File not found for deletion: {filename}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Image not found")

    # Check if it's actually in the upload directory (security check)
    if not str(file_path.resolve()).startswith(
            str(Path(settings.UPLOAD_DIR).resolve())):
        logger.warning(
            f"Security violation: attempt to delete file outside upload dir: {filename}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid file path")

    try:
        file_path.unlink()
        logger.info(
            f"Image deleted successfully: {filename} by {current_user.username}"
        )
        return {"message": f"Image {filename} deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete image {filename}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to delete image")


@router.get(
    "/info",
    summary="Get upload configuration",
    description="Get information about upload limits and supported formats")
async def get_upload_info():
    """Get upload configuration information"""
    return {
        "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
        "supported_extensions": sorted(list(SUPPORTED_IMAGE_EXTENSIONS)),
        "thumbnail_size": {
            "width": THUMBNAIL_SIZE[0],
            "height": THUMBNAIL_SIZE[1]
        },
        "image_quality": DEFAULT_QUALITY
    }
