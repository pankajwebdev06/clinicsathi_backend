import cloudinary
import cloudinary.uploader
from app.core.config import settings

# Configure Cloudinary
if settings.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )

class StorageService:
    @staticmethod
    async def upload_file(file_content: bytes, filename: str, folder: str = "clinic_sathi") -> str:
        """
        Uploads a file to Cloudinary and returns the secure URL.
        """
        try:
            upload_result = cloudinary.uploader.upload(
                file_content,
                public_id=filename.split('.')[0],
                folder=folder,
                resource_type="auto"
            )
            return upload_result.get("secure_url")
        except Exception as e:
            print(f"Cloudinary upload error: {e}")
            raise Exception(f"Failed to upload to Cloudinary: {str(e)}")

    @staticmethod
    async def delete_file(file_url: str):
        """
        Deletes a file from Cloudinary given its URL.
        """
        try:
            # Extract public_id from URL
            # Format: https://res.cloudinary.com/cloud_name/image/upload/v12345/folder/public_id.jpg
            parts = file_url.split('/')
            filename_with_ext = parts[-1]
            public_id = filename_with_ext.split('.')[0]
            
            # If there's a folder (assuming folder structure in URL)
            # This is a bit simplified; a more robust way would be to store public_id in DB
            folder = parts[-2] if "upload" not in parts[-2] else ""
            full_public_id = f"{folder}/{public_id}" if folder else public_id
            
            cloudinary.uploader.destroy(full_public_id)
        except Exception as e:
            print(f"Cloudinary delete error: {e}")

storage_service = StorageService()
