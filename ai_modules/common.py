"""Shared helpers for every detection module: checks, scoring and labels."""

MODE_DEMO = "Demo Analysis Mode"

DISCLAIMER = (
    "AI predictions are indicative only and can be wrong. "
    "Always verify important information through trusted, primary sources before sharing."
)


def sig(name, risk, weight, detail):
    """One explainable check. risk is 0.0 (no concern) to 1.0 (strong concern)."""
    return {
        "name": name,
        "risk": round(max(0.0, min(1.0, risk)), 2),
        "weight": weight,
        "detail": detail,
    }


def classify(score):
    """Map a 0-100 authenticity score to a label and a traffic-light colour."""
    if score >= 70:
        return "Potentially Genuine", "green"
    if score >= 40:
        return "Suspicious", "yellow"
    return "Likely Manipulated", "red"


def build_result(signals, mode, confidence, explanation, recommendations):
    """Combine weighted checks into the final result dictionary."""
    total_weight = sum(s["weight"] for s in signals) or 1
    risk = sum(s["risk"] * s["weight"] for s in signals) / total_weight
    score = round((1 - risk) * 100)
    prediction, color = classify(score)

    indicators = [s["detail"] for s in signals if s["risk"] >= 0.5]
    if not indicators:
        indicators = ["No strong suspicious indicators were found by the checks that ran."]

    return {
        "score": score,
        "prediction": prediction,
        "color": color,
        "confidence": confidence,
        "mode": mode,
        "explanation": explanation,
        "indicators": indicators,
        "recommendations": recommendations,
        "signals": signals,
    }
