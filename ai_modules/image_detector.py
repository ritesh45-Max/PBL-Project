"""AI-generated / manipulated image analysis (demo mode).

Checks used:
- AI tool names written in the file metadata
- Camera information (EXIF make/model)
- Dimensions common in AI generators (multiples of 64)
- Texture detail (very smooth images can be generated or heavily edited)

To add a real model later, replace the body of analyze_image() or call it
from here and keep the same return format.
"""
from PIL import Image, ImageFilter, ImageStat

from .common import MODE_DEMO, build_result, sig

AI_TOOL_KEYWORDS = (
    "stable diffusion", "midjourney", "dall-e", "dalle", "firefly",
    "comfyui", "automatic1111", "novelai", "imagen", "flux",
)
EXIF_SOFTWARE = 305  # "Software" tag
EXIF_MAKE = 271      # camera manufacturer
EXIF_MODEL = 272     # camera model

RECOMMENDATIONS = [
    "Run a reverse image search (Google Lens, TinEye or Bing Visual Search) to find the original.",
    "Look for the earliest version of the image and who first published it.",
    "Check whether reputable news outlets or the people shown have confirmed the photo.",
    "Zoom in on hands, text, reflections, and edges, which AI tools often get wrong.",
    "Remember that many apps remove metadata, so missing camera data is weak evidence alone.",
]


def analyze_image(path):
    try:
        with Image.open(path) as probe:
            probe.verify()
        img = Image.open(path)
    except Exception as exc:
        raise ValueError("This file could not be read as a valid image.") from exc

    with img:
        width, height = img.size
        fmt = img.format or "unknown"
        exif = img.getexif()
        software = str(exif.get(EXIF_SOFTWARE, "")).lower()
        tool = next((k for k in AI_TOOL_KEYWORDS if k in software), None)
        has_camera = bool(exif.get(EXIF_MAKE) or exif.get(EXIF_MODEL))

        typical_size = width % 64 == 0 and height % 64 == 0 and min(width, height) >= 512
        edge_strength = ImageStat.Stat(img.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]
        smooth_risk = 0.6 if edge_strength < 4 else 0.3 if edge_strength < 8 else 0.1

        signals = [
            sig("AI tool metadata", 1.0 if tool else 0.0, 3,
                f"Metadata names an AI generation tool ({tool})" if tool
                else "No AI generation tool named in the metadata"),
            sig("Camera metadata", 0.1 if has_camera else 0.6, 2,
                "Camera make or model information is present" if has_camera
                else "No camera information (EXIF) found"),
            sig("Image dimensions", 0.5 if typical_size else 0.1, 1,
                f"{width}x{height} px matches sizes common in AI generators" if typical_size
                else f"{width}x{height} px shows no AI size pattern"),
            sig("Texture detail", smooth_risk, 1,
                f"Unusually smooth texture (edge detail {edge_strength:.1f})" if smooth_risk >= 0.5
                else f"Natural texture detail (edge detail {edge_strength:.1f})"),
        ]

    explanation = (
        f"Demo analysis of a {fmt} image ({width}x{height} px). The checks look at metadata, "
        "image size and texture only. They cannot prove whether an image is AI-generated or "
        "edited, because high-quality fakes can have clean metadata and realistic texture."
    )
    return build_result(signals, MODE_DEMO, "Low", explanation, RECOMMENDATIONS)
