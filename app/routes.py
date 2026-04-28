import os
import secrets
from PIL import Image
from flask import current_app

class ImageService:
    @staticmethod
    def save_event_image(file_storage) -> str:
        """Handles image optimization and storage with defensive naming."""
        if not file_storage or not file_storage.filename:
            return "default.jpg"

        ext = os.path.splitext(file_storage.filename)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png"}:
            ext = ".jpg"
        
        filename = f"{secrets.token_hex(8)}{ext}"
        upload_path = os.path.join(current_app.root_path, "static/event_pics", filename)

        try:
            img = Image.open(file_storage)
            # Standardize color space
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            # Senior Move: Always resize to prevent high bandwidth costs
            img.thumbnail((1600, 900))
            img.save(upload_path, optimize=True, quality=85)
            return filename
        except Exception as e:
            current_app.logger.error(f"Image processing failed: {e}")
            return "default.jpg"
