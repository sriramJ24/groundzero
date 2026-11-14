"""Biobase challenge, Task A: criteria search over synthetic pathology reports.

Approach: the FINAL DIAGNOSIS block of every report is written by code, so we parse it into
named fields (both layouts: one field per line, or '; '-separated on one line) and answer each
plain-language criterion with an explicit, readable rule over those fields. No model, no labels
from the test set. Every rule is checked against the training answer key before use.

Usage:
  python3 criteria_search.py eval   data/pack_reports          # per-criterion P/R/F1 on train
  python3 criteria_search.py submit data/pack_reports out.json # write the test submission
"""
import json
import re
import sys
from pathlib import Path

FIELDS = sorted({
    "Specimen", "Diagnosis", "Margins", "Tumor size", "Aggressive growth pattern", "Ulceration", "Perineural invasion", "Depth",
    "Pathologic stage", "Depth of invasion", "Lymphovascular invasion", "High-risk features", "Pathologic stage (AJCC 8th ed.)",
    "Invasive carcinoma", "Breslow thickness", "Mitotic rate", "Regression", "Tumor-infiltrating lymphocytes", "Microscopic satellites",
    "Neurotropism", "Extension along follicular epithelium", "Dermal invasion", "Residual melanoma in this excision", "Biopsy correlation",
    "Clark level", "Tumor site", "Histologic type", "Nottingham grade", "Tumor focality", "Ductal carcinoma in situ", "Lymph nodes",
    "Biomarkers", "Neoadjuvant therapy", "Visceral pleural invasion", "Gleason score", "Tumor extent", "Cribriform glands",
    "Intraductal carcinoma", "Extraprostatic extension", "Seminal vesicle invasion", "Histologic grade", "HER2",
    "Macroscopic tumor perforation", "Tumor deposits", "ISUP grade", "Sarcomatoid or rhabdoid features", "Extent of invasion",
}, key=len, reverse=True)
FIELD_RE = re.compile(r"(?:^|\n|;)[ \t]*(" + "|".join(re.escape(f) for f in FIELDS) + r"|Part B, sentinel lymph nodes \([^)]*\)):[ \t]*")


def parse(text: str) -> dict:
    """Report text -> {'sex','age_lo','year','specimen','block', <field>: value, ...}."""
    out = {}
    m = re.search(r"Patient:\s*([MF]), age band (\d+)(?:-\d+|\+)?\s*\|\s*Report year:\s*(\d{4})", text)
    if m:
        out["sex"], out["age_lo"], out["year"] = m.group(1), int(m.group(2)), int(m.group(3))
    m = re.search(r"SPECIMEN:\s*(.*)", text)
    out["specimen"] = m.group(1).strip() if m else ""
    m = re.search(r"FINAL DIAGNOSIS:\s*\n?(.*?)(?:\n\s*\n|\nGROSS DESCRIPTION|\Z)", text, re.S)
    block = m.group(1) if m else ""
    out["block"] = block
    hits = list(FIELD_RE.finditer(block))
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(block)
        out.setdefault(h.group(1), block[h.end():end].strip().rstrip(";").strip())
    out["lead"] = block[: hits[0].start()].strip() if hits else block.strip()  # skin: free diagnosis line
    out["organ"] = organ(out)
    return out


def organ(p: dict) -> str:
    if "Nottingham grade" in p or "Biomarkers" in p: return "breast"
    if "Gleason score" in p: return "prostate"
    if "ISUP grade" in p: return "kidney"
    if "Visceral pleural invasion" in p: return "lung"
    if "Tumor deposits" in p or "Macroscopic tumor perforation" in p: return "colon"
    if "HER2" in p: return "stomach"
    return "skin"


def g(p, f): return (p.get(f) or "").lower()
def present(p, f): return g(p, f).startswith("present")
def absent(p, f): return g(p, f).startswith("not identified")
def num(s, pat):
    m = re.search(pat, s)
    return float(m.group(1)) if m else None
def pos_nodes(p):
    n = num(g(p, "Lymph nodes"), r"(\d+) of \d+ positive")
    return n if n is not None else 0
def stage(p): return p.get("Pathologic stage (AJCC 8th ed.)") or p.get("Pathologic stage") or ""
def size_mm(p):
    s = g(p, "Tumor size")
    v = num(s, r"([\d.]+)\s*mm")
    if v is not None: return v
    v = num(s, r"([\d.]+)\s*cm")
    return v * 10 if v is not None else None
def bio(p, marker):
    m = re.search(marker + r"\s+(positive|negative|equivocal)", g(p, "Biomarkers"))
    return m.group(1) if m else None
def skin_dx(p): return (g(p, "Diagnosis") or p.get("lead", "")).lower()


RULES = {
    "c01": lambda p: p["organ"] == "breast" and bio(p, "her2") == "negative" and pos_nodes(p) >= 1,
    "c02": lambda p: p["organ"] == "breast" and bio(p, "er") == "positive" and bio(p, "pr") == "negative",
    "c03": lambda p: p["organ"] == "breast" and bio(p, "er") == "negative" and bio(p, "pr") == "negative" and bio(p, "her2") == "negative",
    "c04": lambda p: p["organ"] == "breast" and present(p, "Lymphovascular invasion") and (size_mm(p) or 0) > 20,
    "c05": lambda p: p["organ"] == "breast" and g(p, "Margins").startswith("negative") and (num(g(p, "Margins"), r"invasive carcinoma is ([\d.]+) mm") or 99) <= 3,
    "c06": lambda p: p["organ"] == "breast" and g(p, "Tumor focality").startswith("multifocal") and p.get("age_lo", 999) < 60,
    "c07": lambda p: p["organ"] == "breast" and g(p, "Nottingham grade").startswith("3") and absent(p, "Lymphovascular invasion"),
    # the key counts pN1c (tumor deposits, no positive nodes) as stage III, so use the stage line, not the node count
    "c08": lambda p: p["organ"] == "colon" and re.search(r"pn[12]", stage(p).lower()) is not None,
    "c09": lambda p: p["organ"] == "colon" and g(p, "Histologic type").startswith("mucinous"),
    "c10": lambda p: p["organ"] == "colon" and present(p, "Tumor deposits"),
    "c11": lambda p: p["organ"] == "colon" and pos_nodes(p) == 0 and present(p, "Lymphovascular invasion"),
    "c12": lambda p: p["organ"] == "colon" and "pt4" in stage(p).lower(),
    "c13": lambda p: p["organ"] == "colon" and (size_mm(p) or 0) >= 50 and absent(p, "Perineural invasion"),
    "c14": lambda p: p["organ"] == "lung" and present(p, "Visceral pleural invasion"),
    "c15": lambda p: p["organ"] == "lung" and "squamous" in g(p, "Histologic type") and "bronchial margin involved" in g(p, "Margins"),
    "c16": lambda p: p["organ"] == "lung" and "adenocarcinoma" in g(p, "Histologic type") and pos_nodes(p) >= 1,
    "c17": lambda p: p["organ"] == "prostate" and (num(g(p, "Gleason score"), r"grade group (\d)") or 0) >= 4,
    "c18": lambda p: p["organ"] == "prostate" and present(p, "Seminal vesicle invasion"),
    "c19": lambda p: p["organ"] == "prostate" and g(p, "Margins").startswith("positive") and absent(p, "Extraprostatic extension"),
    "c20": lambda p: p["organ"] == "prostate" and present(p, "Perineural invasion") and absent(p, "Lymphovascular invasion"),
    "c21": lambda p: p["organ"] == "stomach" and g(p, "HER2").startswith("positive"),
    "c22": lambda p: p["organ"] == "stomach" and g(p, "Histologic type").startswith("poorly cohesive") and pos_nodes(p) >= 1,
    "c23": lambda p: p["organ"] == "stomach" and "pt4" in stage(p).lower(),
    "c24": lambda p: p["organ"] == "kidney" and "clear cell" in g(p, "Histologic type") and (num(g(p, "ISUP grade"), r"(\d)") or 0) >= 3,
    "c25": lambda p: p["organ"] == "kidney" and present(p, "Sarcomatoid or rhabdoid features"),
    "c26": lambda p: p["organ"] == "kidney" and re.search(r"renal vein|vena cava", g(p, "Extent of invasion")) is not None,
    "c27": lambda p: p["organ"] == "skin" and "basal cell carcinoma" in skin_dx(p) and re.search(r"extends to the (peripheral and )?deep margin|deep margin (is )?(involved|positive)|extends to the peripheral and deep margins|deep margins? involved", g(p, "Margins")) is not None,
    "c28": lambda p: p["organ"] == "skin" and "invasive squamous cell carcinoma" in skin_dx(p) and re.search(r"\(g[23]\)|moderately|poorly", skin_dx(p)) is not None,
    "c29": lambda p: p["organ"] == "colon" and pos_nodes(p) >= 1 and p.get("age_lo", -1) >= 70,
    "c30": lambda p: p["organ"] == "lung" and p.get("sex") == "F" and p.get("year") in (2023, 2024),
}


def answer(rows):
    parsed = [(r["id"], parse(r["report_text"])) for r in rows]
    return {cid: [i for i, p in parsed if rule(p)] for cid, rule in RULES.items()}


def load(path): return [json.loads(line) for line in open(path)]


def main():
    mode, pack = sys.argv[1], Path(sys.argv[2])
    if mode == "eval":
        rows = load(pack / "train.jsonl")
        truth = json.load(open(pack / "criteria_train_answers.json"))
        organ_ok = sum(parse(r["report_text"])["organ"] == r["labels"]["organ"] for r in rows)
        print(f"organ parsed correctly: {organ_ok}/{len(rows)}")
        pred = answer(rows)
        f1s = []
        for cid in sorted(RULES):
            t, a = set(truth[cid]), set(pred[cid])
            tp = len(t & a)
            pr = tp / len(a) if a else 0.0
            rc = tp / len(t) if t else 0.0
            f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
            f1s.append(f1)
            flag = "" if f1 == 1 else "  <-- check"
            print(f"{cid}  P {pr:.3f}  R {rc:.3f}  F1 {f1:.3f}  true {len(t):4d}  ours {len(a):4d}{flag}")
        print(f"mean F1 on train: {sum(f1s) / len(f1s):.4f}")
        out = pack.parent / "train_eval.json"
        json.dump({"mean_f1": sum(f1s) / len(f1s), "n_reports": len(rows), "per_criterion_f1": dict(zip(sorted(RULES), f1s))}, open(out, "w"), indent=1)
    else:
        rows = load(pack / "test.jsonl")
        pred = answer(rows)
        sub = {cid: {"ids": ids, "count": len(ids)} for cid, ids in pred.items()}
        json.dump(sub, open(sys.argv[3], "w"), indent=1)
        print(f"wrote {sys.argv[3]}: {len(rows)} test reports, {sum(len(v) for v in pred.values())} matches across {len(pred)} criteria")
        print({c: len(v) for c, v in pred.items()})


if __name__ == "__main__":
    main()
