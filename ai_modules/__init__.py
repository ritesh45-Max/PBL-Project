"""AI detection modules. Each module is separate so trained models can be swapped in later."""
from .common import DISCLAIMER, MODE_DEMO
from .text_detector import analyze_text
from .image_detector import analyze_image
from .video_detector import analyze_video

__all__ = ["analyze_text", "analyze_image", "analyze_video", "DISCLAIMER", "MODE_DEMO"]
