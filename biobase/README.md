# Biobase challenge: Find the Right Patients

A separate, small entry for the Biobase sponsor challenge at DNA Forge (Nov 14, 2026). It is independent of the GroundZero farm dashboard and uses only Biobase's own synthetic pathology reports. No agricultural data is involved, and nothing here is for medical use.

## Results on the held-out answer key

Scored by the challenge page's self-evaluation after the 4:00 PM key release, on files frozen (and committed) before it.

| Task | Our score | Organizers' baseline |
|---|---|---|
| Criteria search (30 criteria, 979 test reports) | mean F1 **1.000**, 30 of 30 answered, mean count error 0.0% | keyword baseline, mean F1 0.27 |
| Slide organ labels (67 held-out slides) | accuracy **79.1%** | about 70% (Prov-GigaPath nearest neighbour) |
| Similar slides | precision at 1 **0.836**, at 5 **0.779**, at 10 **0.765** | about 0.8, 0.7, 0.6 |

The slide organ accuracy on the held-out set (79.1%) is lower than the 85.0% cross-validated estimate below, as expected from picking the best of 28 configurations; with 67 slides, one slide is 1.5 points.

## What it does

For each of the 30 plain-language criteria (for example "Colon cancer with no positive lymph nodes and lymphovascular invasion present"), it lists the matching report ids among the 979 unlabelled test reports, with a count.

## How

The final diagnosis block of each report is written by code, so `criteria_search.py` parses it into named fields (handling both layouts: one field per line, or `; `-separated on one line), then answers each criterion with one explicit, readable rule over those fields. There is no model and no API call, so every match can be traced to the exact field that produced it. Negations ("not identified"), numbers (tumor size in mm or cm, margin distance, node counts, Grade Group) and combined fields are handled in the rules.

## Measured before the key opened

- On the 9,010 labelled training reports, against the provided answer key: **mean F1 1.0000** across all 30 criteria (the provided keyword baseline is 0.27). Organ is inferred from the report text correctly for 9,010 of 9,010.
- The rules were written and corrected using the training reports and their key only. Two rules were adjusted after the first pass (0.9996): stage III colon cancer follows the stage line, because the key counts pN1c tumor deposits as node-positive; and "margins involved" wording for basal cell carcinoma.
- `submission_criteria.json` was frozen before the 4:00 PM answer-key release; the held-out result is in the table above.

## Known limits

- This works because the diagnosis block is templated. Free-text reports from real hospitals would need a language model or a much broader parser, and that has not been tested here.
- One criterion is ambiguous in a way the training data cannot settle: "node-positive colon cancer in patients 70 or older" could mean positive nodes or a pN1c stage with deposits only. No training or test report distinguishes the two readings, so it does not affect this submission.

## Slide tasks (C1 organ labels, C2 similar slides)

`slides.py` predicts the organ group of the 67 held-out slides and lists the 10 most similar slides for each, using only the provided slide-level embeddings and unlabelled slide metadata (sex, supplier, magnification, scanner).

- **Model:** logistic regression on Prov-GigaPath slide vectors plus metadata. It was chosen by 5-fold cross-validation on the 190 labelled slides, comparing four embedding models, combinations of them, and nearest-neighbour matching.
- **Measured (labelled slides only):** 5-fold cross-validated organ accuracy **0.850** on 180 slides (organ groups with at least 5 slides). Nearest-neighbour on the same GigaPath vectors gets 0.784 leave-one-out. The chosen configuration was the best of 28 tried, so 0.850 is somewhat optimistic; the nearest alternatives scored 0.79 to 0.84.
- **Similar slides:** cosine similarity on the embedding, boosted when two slides have the same known or predicted organ. This part has no cross-validated number.
- Both CSVs were frozen before the 4:00 PM key release; held-out results are in the table above. With 67 slides over 15 groups, the organizers themselves call the score a rough signal.
- Rare groups (Esophagus, Skin, Bone) have very few labelled slides, so predictions there are weak. Two slides have no GigaPath vector and are predicted from metadata alone.

Needs `numpy` and `scikit-learn`, plus the "Slide metadata" and "Slide tiles" packs unzipped into `biobase/data/`.

```bash
python biobase/slides.py biobase/data
```

## Run (criteria search)

Download the "Synthetic reports" pack from the challenge page and unzip it into `biobase/data/` (the data is not committed).

```bash
python3 biobase/criteria_search.py eval biobase/data/pack_reports
```

```bash
python3 biobase/criteria_search.py submit biobase/data/pack_reports biobase/submission_criteria.json
```
