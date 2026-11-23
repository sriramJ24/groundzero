# Decisions

The record of decisions for GroundZero. Cotal keeps only 7 days of history, so anything decided there that still matters next week goes here, through a PR.

Newest first. Each entry: date, decision, why, who decided. Don't rewrite old entries; if a decision changes, add a new one that says which entry it replaces.

---

### 2026-11-21: GPU jobs run on Tushar's laptop

- **Decision:** GPU jobs run on Tushar's laptop (RTX 3070 Laptop GPU, 8 GB VRAM; CUDA memory test passed). This replaces "GPU PC" in the entries below.
- **Why:** That's the GPU available. 8 GB is enough for small-section splats if image count and resolution stay modest.
- **Decided by:** Tushar, Sriram

### 2026-11-21: Capture format 0.1-draft agreed

- **Decision:** The Pi and cloud build against `docs/capture-format.md` as merged in PR #3: one full-resolution JPEG plus a same-stem JSON; GPS, orientation and height nullable; pivot fields optional; capture order by the numeric sequence suffix; JSON uploaded after the JPEG as the ready marker. Sample pair in `docs/samples/` (a synthetic test pattern, not a camera photo).
- **Why:** Lets ingestion and the Pi be built in parallel before the GPS and angle hardware is chosen.
- **Decided by:** Tushar (proposed), Sriram (approved)

### 2026-11-21: Ownership split confirmed

- **Decision:** Tushar confirmed the ownership split below: Pi capture/upload and GPU work, including exporting the photoreal 3D asset. Sriram owns ingestion, the viewer and the dashboard.
- **Decided by:** Tushar, Sriram

### 2026-11-21: Repo is the record, Cotal is the conversation

- **Decision:** Agents coordinate live in Cotal (Sriram's Claude Code as `pipeline`, Tushar's Codex as `gpu-trainer`). Decisions, formats and job results that matter later are written into this repo.
- **Why:** Cotal history expires after 7 days.
- **Decided by:** Sriram (Tushar confirms by approving the PR that added this)

### 2026-11-21: Ownership split

- **Decision:** Tushar owns Pi capture and upload, and GPU jobs (training, photoreal 3D). Sriram owns cloud processing, the 3D viewer and the dashboard. Each person works in their own folders (see `CLAUDE.md` / `AGENTS.md`).
- **Why:** Tushar has the hardware and the GPU PC; Sriram has the processing and viewer code.
- **Decided by:** Sriram (Tushar confirms by approving the PR that added this)

### 2026-11-21: Pi only captures and uploads

- **Decision:** The Raspberry Pi 5 on the pivot captures photos, writes a JSON metadata file per photo, and uploads both. All processing (3D models, crop height, health flags) runs in the cloud.
- **Why:** Keeps the device cheap and simple, and lets processing change without touching the hardware.
- **Decided by:** Sriram (Tushar confirms by approving the PR that added this)

### 2026-11-21: Big files go through links

- **Decision:** Datasets, model weights and 3D outputs over about 50 MB are shared as GitHub release assets or Google Drive links, never committed.
- **Why:** Keeps the repo small and Cotal messages within limits.
- **Decided by:** Sriram (Tushar confirms by approving the PR that added this)

### 2026-11-21: Photoreal (splat) view is a GPU job

- **Decision:** CPU-trained Gaussian splats were too coarse, so photoreal 3D is trained on Tushar's GPU PC. The viewer shows its Photoreal button only when splat data is present (`viewer/field3d/splat/section_splat.json`).
- **Why:** No paid GPU for now, and CPU results weren't good enough.
- **Decided by:** Sriram

### 2026-11-20: Hardware concept "PivotCam V1"

- **Decision:** Raspberry Pi 5 (4 GB), Camera Module 3 (standard), 128 GB microSD, mounted on the pivot pipe, camera about 35° down.
- **Decided by:** Sriram (Tushar confirms by approving the PR that added this)

### 2026-11-20: Never fabricate data

- **Decision:** Crop condition shows "not assessed" until it is actually measured. Unmeasured fields are stored empty. No invented health scores or accuracy figures.
- **Decided by:** Sriram
