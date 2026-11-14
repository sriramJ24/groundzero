"""Transparent, indicative zone health rule (not agronomic ground truth).

Per capture penalty: healthy 0, discoloration 35, wilting 60, scaled by confidence.
Rejected reviews ignored. Newest 5 captures, recency weights 1,.8,.6,.4,.2.
score = clamp(100 - weighted-average penalty).
"""
PENALTY = {"healthy": 0.0, "discoloration": 35.0, "wilting": 60.0}
WEIGHTS = [1.0, 0.8, 0.6, 0.4, 0.2]
METHOD = "indicative rule-based"


def _ts(c):
    return c.get("captured_at") or c.get("received_at") or ""


def zone_health(captures_for_zone, seeded_health):
    caps = [c for c in (captures_for_zone or [])
            if (c.get("review") or {}).get("status") != "rejected"]
    if not caps:
        return seeded_health
    # newest first; stable on id as tiebreak (ids increase over time)
    caps.sort(key=lambda c: (c.get("received_at") or "", _ts(c), str(c.get("id"))), reverse=True)
    recent = caps[:5]
    num = den = 0.0
    mix = {}
    for c, w in zip(recent, WEIGHTS):
        ep = c.get("edge_prediction") or {}
        label = ep.get("label")
        conf = max(0.0, min(1.0, float(ep.get("confidence") or 0)))
        pen = PENALTY.get(label, 0.0) * conf
        num += w * pen
        den += w
        mix[label] = mix.get(label, 0) + 1
    score = max(0.0, min(100.0, 100.0 - (num / den if den else 0.0)))
    ep0 = recent[0].get("edge_prediction") or {}
    return {
        "score": round(score, 1),
        "last_label": ep0.get("label"),
        "last_confidence": ep0.get("confidence"),
        "n_captures": len(recent),
        "label_mix": mix,
        "method": METHOD,
    }
