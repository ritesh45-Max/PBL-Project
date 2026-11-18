"""Fake-news text analysis.

Two modes:
1. Trained model: if models/fake_news_model.joblib exists, it is used.
   The model must be a scikit-learn pipeline with predict_proba(), where
   column 1 is the probability of "fake".
2. Demo heuristics: transparent style-based checks. These are NOT genuine AI
   detection and are labelled as demo mode in the results.
"""
import re
from functools import lru_cache
from pathlib import Path

from .common import MODE_DEMO, build_result, sig

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "fake_news_model.joblib"

SENSATIONAL_WORDS = [
    "shocking", "unbelievable", "breaking", "exposed", "secret", "miracle", "hoax",
    "urgent", "bombshell", "you won't believe", "must share", "share before",
    "banned", "viral", "deleted",
]
EMOTIONAL_WORDS = [
    "outrage", "terrifying", "horrifying", "furious", "disgusting", "panic",
    "destroyed", "evil", "traitor",
]
CONSPIRACY_PHRASES = [
    "they don't want you to know", "mainstream media", "wake up", "big pharma",
    "government hiding", "the truth about", "what they are hiding", "cover-up",
]
SOURCE_PATTERN = re.compile(
    r"according to|source|study|research|report|official|https?://|\(\d{4}\)", re.IGNORECASE)

RECOMMENDATIONS = [
    "Check whether the claim appears on at least two trusted news outlets or official websites.",
    "Find the original source, author and publication date before believing or sharing.",
    "Search reputable fact-checking organisations for the headline or key claim.",
    "Be careful of content that pressures you to share urgently or provokes strong fear or anger.",
    "Look for supporting evidence such as official statements, documents or data, not just screenshots.",
]


@lru_cache(maxsize=1)
def _load_trained_model():
    """Load the trained model once. Returns None if it is not available."""
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def analyze_text(text):
    model = _load_trained_model()
    if model is not None:
        return _analyze_with_model(text, model)
    return _analyze_heuristic(text)


def _analyze_with_model(text, model):
    prob_fake = float(model.predict_proba([text])[0][1])
    signals = [sig(
        "Trained classifier", prob_fake, 1,
        f"Trained model estimated a {round(prob_fake * 100)}% likelihood that the text is misleading",
    )]
    explanation = ("This result comes from a trained text classifier. It estimates how similar "
                   "the text is to examples it was trained on. It does not verify the facts "
                   "themselves, so always check the claims with trusted sources.")
    return build_result(signals, "Trained Model", "Medium", explanation, RECOMMENDATIONS)


def _analyze_heuristic(text):
    lower = text.lower()
    words = re.findall(r"[A-Za-z']+", text)
    word_count = max(1, len(words))
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    signals = []

    hits = [w for w in SENSATIONAL_WORDS if w in lower]
    signals.append(sig(
        "Sensational language", len(hits) / 3, 2,
        f"Sensational phrases found: {', '.join(hits)}" if hits
        else "No sensational phrases found"))

    hits = [w for w in EMOTIONAL_WORDS if w in lower]
    signals.append(sig(
        "Emotional pressure", len(hits) / 3, 1.5,
        f"Strong emotional wording found: {', '.join(hits)}" if hits
        else "Neutral emotional tone"))

    hits = [p for p in CONSPIRACY_PHRASES if p in lower]
    signals.append(sig(
        "Conspiracy-style phrasing", len(hits) / 2, 2,
        f"Conspiracy-style phrases found: {', '.join(hits)}" if hits
        else "No conspiracy-style phrasing"))

    exclamations = text.count("!")
    ratio = exclamations / sentences
    signals.append(sig(
        "Exclamation overuse", ratio / 0.5, 1,
        f"{exclamations} exclamation marks across {sentences} sentences"))

    caps = [w for w in words if len(w) > 2 and w.isupper()]
    signals.append(sig(
        "Excessive capitals", (len(caps) / word_count) / 0.2, 1,
        f"{len(caps)} fully capitalised words" if caps else "Normal capitalisation"))

    has_source = bool(SOURCE_PATTERN.search(text))
    signals.append(sig(
        "Source references", 0.15 if has_source else 0.8, 2,
        "Mentions a source, study, report or link" if has_source
        else "No sources, citations or links mentioned"))

    short = word_count < 40
    signals.append(sig(
        "Context length", 0.6 if short else 0.1, 1,
        "Very short text gives little context to verify" if short
        else "Enough context to check the claims"))

    explanation = (
        "Demo analysis: this result uses transparent rule-based checks on writing style, "
        "including sensational wording, emotional pressure, conspiracy phrasing, capital "
        "letters, exclamation marks and whether sources are cited. These checks do not test "
        "whether the facts are true, so a well-written false story can pass and a genuine "
        "but dramatic story can be flagged."
    )
    return build_result(signals, MODE_DEMO, "Low", explanation, RECOMMENDATIONS)
