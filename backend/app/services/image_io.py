from io import BytesIO
from PIL import Image, ImageOps
import cv2
import numpy as np


def load_image(data: bytes, max_side: int) -> tuple[np.ndarray, int, int]:
    image = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    array = np.asarray(image)
    bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
    return bgr, bgr.shape[1], bgr.shape[0]
