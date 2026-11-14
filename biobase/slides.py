"""Biobase challenge, Tasks C1 (organ labels) and C2 (similar slides) for the 67 held-out slides.

Uses only the provided slide-level embeddings (four models) and slide metadata. Model choice is made
by cross-validation on the labelled slides only; nothing is tuned on the held-out set.

Usage: python slides.py data            # prints CV results, writes submission_slides_organ.csv / _similar.csv
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import normalize

root = Path(sys.argv[1])
manifest = json.load(open(root / "pack_slides" / "slides_manifest.json"))
slides = manifest if isinstance(manifest, list) else manifest.get("slides", manifest)
ids = [s["id"] for s in slides]
MODELS = ["gigapath", "biomedclip", "hoptimus", "dinov2"]


def vectors(model):
    raw = json.load(open(root / "tilepack" / "embeddings" / model / "slide-vectors.json"))
    d = {r["id"]: np.asarray(r["v"], dtype=np.float32) for r in raw}
    dim = len(next(iter(d.values())))
    m = np.stack([d.get(i, np.zeros(dim, np.float32)) for i in ids])
    return normalize(m - m[[i in d for i in ids]].mean(0)) * np.array([[i in d] for i in ids])


V = {m: vectors(m) for m in MODELS}
group = np.array([s.get("organGroup") or "" for s in slides], dtype=object)
held = np.array([bool(s.get("heldout")) for s in slides])
lab = (~held) & (group != "")
print(f"{len(ids)} slides, {lab.sum()} labelled with organ group, {held.sum()} held out")

# metadata that is present on held-out slides too (no labels): sex, supplier, magnification
def meta():
    cols = []
    for key in ("sex", "supplierId", "magnification", "scanner"):
        vals = sorted({str(s.get(key)) for s in slides})
        cols += [[float(str(s.get(key)) == v) for s in slides] for v in vals]
    return np.array(cols, dtype=np.float32).T


M = meta()
y = group[lab]
classes, counts = np.unique(y, return_counts=True)
n_splits = 5
keep = np.isin(y, classes[counts >= n_splits])  # CV needs enough members per class; rare classes still train the final model
cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=0)


def feats(names, with_meta):
    x = np.hstack([V[n] for n in names])
    return np.hstack([x, 0.5 * M]) if with_meta else x


def knn1(X):
    Xl = X[lab]
    sim = Xl @ Xl.T
    np.fill_diagonal(sim, -9)
    return float((y[sim.argmax(1)] == y).mean())


results = []
for names in (["gigapath"], ["biomedclip"], ["hoptimus"], ["gigapath", "biomedclip"], ["gigapath", "hoptimus"], ["gigapath", "biomedclip", "hoptimus"], MODELS):
    for with_meta in (False, True):
        X = feats(names, with_meta)
        for C in (1.0, 10.0):
            clf = LogisticRegression(C=C, max_iter=3000)
            pred = cross_val_predict(clf, X[lab][keep], y[keep], cv=cv)
            results.append((float((pred == y[keep]).mean()), "+".join(names), with_meta, C))
        if not with_meta:
            print(f"  1-NN leave-one-out, {'+'.join(names):32s} {knn1(normalize(X)):.3f}")
results.sort(reverse=True)
for acc, n, wm, C in results[:8]:
    print(f"  logistic 5-fold  {n:32s} meta={wm!s:5s} C={C:<4} acc {acc:.3f}")
acc, n, wm, C = results[0]
names = n.split("+")
print(f"chosen: {n}, meta={wm}, C={C}; cross-validated accuracy {acc:.3f} on {keep.sum()} labelled slides (classes with >= {n_splits} slides)")

X = feats(names, wm)
clf = LogisticRegression(C=C, max_iter=3000).fit(X[lab], y)
proba_all = clf.predict_proba(X)
pred_held = clf.classes_[proba_all[held].argmax(1)]
out = Path(__file__).parent
with open(out / "submission_slides_organ.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["slide_id", "organ"])
    for i, p in zip(np.array(ids)[held], pred_held): w.writerow([i, p])

# C2: similarity = cosine on the embedding, plus agreement of predicted organ distributions.
# Labelled slides use their known organ as a one-hot distribution; held-out slides use the classifier's probabilities.
P = proba_all.copy()
for k in np.where(lab)[0]:
    P[k] = (clf.classes_ == group[k]).astype(float)
E = normalize(np.hstack([V[m] for m in names]))
S = E @ E.T + 1.5 * (normalize(P) @ normalize(P).T)
np.fill_diagonal(S, -9)
with open(out / "submission_slides_similar.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["query_slide_id", "rank", "result_slide_id"])
    for q in np.where(held)[0]:
        for r, j in enumerate(np.argsort(-S[q])[:10], 1): w.writerow([ids[q], r, ids[j]])

json.dump({"chosen": {"embeddings": names, "metadata": bool(wm), "C": C}, "cv_accuracy": acc, "cv_n": int(keep.sum()), "cv_folds": n_splits,
           "top_configs": [{"acc": a, "embeddings": nn, "metadata": bool(m), "C": c} for a, nn, m, c in results[:8]],
           "held_out_predictions": dict(zip(*np.unique(pred_held, return_counts=True)))}, open(out / "slides_cv.json", "w"), indent=1, default=int)
print("held-out predictions:", dict(zip(*np.unique(pred_held, return_counts=True))))
