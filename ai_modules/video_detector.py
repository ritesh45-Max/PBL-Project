"""Deepfake / manipulated video analysis (demo mode).

If OpenCV is installed, the module samples frames and measures:
- how irregular frame-to-frame changes are (flicker/instability)
- how stable sharpness is across frames
- resolution

Without OpenCV only file-level information is used.
Real deepfake detection needs a trained face-analysis model; plug it in here later.
"""
import os
import statistics

from .common import MODE_DEMO, build_result, sig

RECOMMENDATIONS = [
    "Search for the same clip on the original channel or from the person or organisation it claims to show.",
    "Check whether trusted news outlets have verified the video before sharing it.",
    "Watch for unnatural lip movement, blinking, lighting changes and audio that does not match.",
    "Look at the full context: who uploaded it, when, and whether a longer version exists.",
    "Use reverse video search tools or extract a frame and run a reverse image search.",
]


def analyze_video(path):
    try:
        import cv2
    except ImportError:
        cv2 = None

    if cv2 is None:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        signals = [sig(
            "File information", 0.3, 1,
            f"Video is {size_mb:.1f} MB. Frame analysis needs OpenCV "
            "(pip install opencv-python-headless).")]
        explanation = ("Only file-level information was available, so this result is very limited. "
                       "Install OpenCV to enable frame-based checks.")
        return build_result(signals, "Demo Analysis Mode (file checks only)", "Low",
                            explanation, RECOMMENDATIONS)

    return _analyze_frames(path, cv2)


def _analyze_frames(path, cv2):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise ValueError("The video could not be opened. Try an MP4 or WebM file.")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if total < 10:
        cap.release()
        raise ValueError("The video is too short to analyse.")

    samples = min(30, total)
    step = max(1, total // samples)
    frames = []
    for index in range(0, total, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(cv2.resize(gray, (320, 180)))
        if len(frames) == samples:
            break
    cap.release()

    if len(frames) < 3:
        raise ValueError("Not enough readable frames were found in this video.")

    diffs = [float(cv2.absdiff(a, b).mean()) for a, b in zip(frames, frames[1:])]
    variability = statistics.pstdev(diffs) / (statistics.mean(diffs) + 1e-6)
    flicker_risk = min(1.0, max(0.0, (variability - 0.6)))

    sharpness = [float(cv2.Laplacian(f, cv2.CV_64F).var()) for f in frames]
    sharp_cv = statistics.pstdev(sharpness) / (statistics.mean(sharpness) + 1e-6)
    sharp_risk = min(1.0, max(0.0, (sharp_cv - 0.5)))

    low_res = width < 480 or height < 320
    signals = [
        sig("Frame-to-frame consistency", flicker_risk, 2,
            f"Changes between frames are irregular (variability {variability:.2f})"
            if flicker_risk >= 0.5
            else f"Changes between frames are steady (variability {variability:.2f})"),
        sig("Sharpness consistency", sharp_risk, 1.5,
            f"Sharpness varies unevenly across frames (variation {sharp_cv:.2f})"
            if sharp_risk >= 0.5
            else f"Sharpness is consistent across frames (variation {sharp_cv:.2f})"),
        sig("Resolution", 0.4 if low_res else 0.1, 1,
            f"Low resolution ({width}x{height}) can hide manipulation artefacts" if low_res
            else f"Resolution ({width}x{height}) is adequate for checks"),
    ]

    duration = total / fps if fps else 0
    explanation = (
        f"Demo frame analysis of {len(frames)} sampled frames from a {duration:.1f}-second "
        f"{width}x{height} video. These checks look for irregular changes and uneven sharpness, "
        "which can appear in some manipulated or AI-generated videos. They do not detect faces "
        "or lip-sync, so they cannot confirm a deepfake on their own."
    )
    return build_result(signals, "Demo Analysis Mode (OpenCV frame statistics)", "Low",
                        explanation, RECOMMENDATIONS)
