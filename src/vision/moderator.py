"""OpenCV + YOLO модерация изображений для NFT/аватаров."""
import logging
from io import BytesIO

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Категории к блокировке (YOLO COCO)
_BLOCKED_CLASSES = {"weapon", "knife", "gun", "rifle", "pistol"}

_yolo_model = None


def _get_yolo():
    global _yolo_model
    if _yolo_model is None:
        try:
            from ultralytics import YOLO
            _yolo_model = YOLO("yolov8n.pt")   # nano — CPU-friendly
            logger.info("YOLO model loaded")
        except Exception as e:
            logger.warning(f"YOLO not available: {e}")
    return _yolo_model


def _check_basic_cv(img: np.ndarray) -> dict:
    """Базовые OpenCV проверки: разрешение, формат, NSFW-цвет эвристика."""
    h, w = img.shape[:2]
    if h < 32 or w < 32:
        return {"ok": False, "reason": "image too small"}
    if h > 8000 or w > 8000:
        return {"ok": False, "reason": "image too large"}
    # Простая эвристика skin-тонов
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 20, 70])
    upper = np.array([20, 150, 255])
    mask = cv2.inRange(hsv, lower, upper)
    skin_ratio = mask.sum() / (h * w * 255)
    if skin_ratio > 0.6:
        return {"ok": False, "reason": "high skin-tone ratio (potential NSFW)"}
    return {"ok": True, "reason": None}


def moderate_image(image_bytes: bytes) -> dict:
    """
    Проверяет изображение (bytes).
    Returns: {"flagged": bool, "reason": str|None, "detections": list}
    """
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"flagged": True, "reason": "cannot decode image", "detections": []}

    basic = _check_basic_cv(img)
    if not basic["ok"]:
        return {"flagged": True, "reason": basic["reason"], "detections": []}

    detections = []
    model = _get_yolo()
    if model is not None:
        try:
            results = model(img, verbose=False)
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = model.names.get(cls_id, "")
                    conf = float(box.conf[0])
                    detections.append({"class": cls_name, "confidence": round(conf, 3)})
                    if cls_name.lower() in _BLOCKED_CLASSES and conf > 0.4:
                        return {
                            "flagged": True,
                            "reason": f"detected: {cls_name} (conf={conf:.2f})",
                            "detections": detections,
                        }
        except Exception as e:
            logger.warning(f"YOLO inference error: {e}")

    return {"flagged": False, "reason": None, "detections": detections}
