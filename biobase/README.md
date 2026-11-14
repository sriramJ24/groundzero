# Biobase challenge: Find the Right Patients (Task A, criteria search)

A separate, small entry for the Biobase sponsor challenge at DNA Forge (Nov 14, 2026). It is independent of the FIELDOS farm dashboard and uses only Biobase's own synthetic pathology reports. No agricultural data is involved, and nothing here is for medical use.

## What it does

For each of the 30 plain-language criteria (for example "Colon cancer with no positive lymph nodes and lymphovascular invasion present"), it lists the matching report ids among the 979 unlabelled test reports, with a count.

## How

The final diagnosis block of each report is written by code, so `criteria_search.py` parses it into named fields (handling both layouts: one field per line, or `; `-separated on one line), then answers each criterion with one explicit, readable rule over those fields. There is no model and no API call, so every match can be traced to the exact field that produced it. Negations ("not identified"), numbers (tumor size in mm or cm, margin distance, node counts, Grade Group) and combined fields are handled in the rules.

## Measured so far

- On the 9,010 labelled training reports, against the provided answer key: **mean F1 1.0000** across all 30 criteria (the provided keyword baseline is 0.27). Organ is inferred from the report text correctly for 9,010 of 9,010.
- The rules were written and corrected using the training reports and their key only. Two rules were adjusted after the first pass (0.9996): stage III colon cancer follows the stage line, because the key counts pN1c tumor deposits as node-positive; and "margins involved" wording for basal cell carcinoma.
- **Test score: not known when this was written.** `submission_criteria.json` was frozen before the 4:00 PM answer-key release. The test result should be read from the challenge page's self-evaluation, not assumed from the training score.

## Known limits

- This works because the diagnosis block is templated. Free-text reports from real hospitals would need a language model or a much broader parser, and that has not been tested here.
- One criterion is ambiguous in a way the training data cannot settle: "node-positive colon cancer in patients 70 or older" could mean positive nodes or a pN1c stage with deposits only. No training or test report distinguishes the two readings, so it does not affect this submission.
- Tasks B and C (slide organ labels, similar slides) were not attempted.

## Run

Download the "Synthetic reports" pack from the challenge page and unzip it into `biobase/data/` (the data is not committed).

```bash
python3 biobase/criteria_search.py eval biobase/data/pack_reports
```

```bash
python3 biobase/criteria_search.py submit biobase/data/pack_reports biobase/submission_criteria.json
```
