# GroundZero: instructions for coding agents

`CLAUDE.md` (read by Claude Code) and `AGENTS.md` (read by Codex) hold the same text. If you change one, copy the change to the other in the same PR.

## Goal

A camera on a center-pivot irrigation arm that gives a farmer a 3D view of the field, flags where the crop looks unhealthy, and keeps the original photo as evidence for every flag.

- **On the pivot:** a Raspberry Pi 5 with a Camera Module 3, mounted on the pivot pipe and angled about 35° down. It only captures photos and uploads them. No processing happens on the Pi beyond writing the metadata file.
- **In the cloud:** photos are turned into 3D field models and crop-health flags, which the 3D viewer and the dashboard show.

Never invent data. If something wasn't measured (GPS, crop health, accuracy), store it as empty and show it as "not measured" or "not assessed".

## Architecture

```
Pi 5 on pivot ──photo + JSON──▶ upload ──▶ cloud storage
                                               │
                                cloud processing (CPU)
                                ├─ 3D field model per pass
                                ├─ crop height / health flags
                                └─ links each flag to its photos
                                               │
                     GPU jobs (training, photoreal 3D) when needed
                                               │
                          3D viewer + dashboard for the farmer
```

The photo and its metadata format are defined in [docs/capture-format.md](docs/capture-format.md). Both sides build against that file.

## Who owns what

| Area | Owner | Agent | Folders |
|---|---|---|---|
| Pi capture and upload | Tushar (TMRmehta) | Codex, `gpu-trainer` | `pi/`, `hardware/` (older ESP32 work) |
| GPU jobs: model training, photoreal 3D (splats) | Tushar | Codex, `gpu-trainer` | `gpu/` |
| Cloud processing | Sriram (sriramJ24) | Claude Code, `pipeline` | `pipelines/`, `backend/` |
| 3D viewer and dashboard | Sriram | Claude Code, `pipeline` | `viewer/`, `frontend/` |
| Shared contracts and decisions | Both | Both | `docs/`, `shared/` |

Rules:

- Work only in your own folders. If you need a change in someone else's folder, ask in Cotal or open an issue; don't edit it.
- `docs/` and `shared/` are shared. A change there needs a PR that the other person approves.
- Create `pi/` or `gpu/` when the first code for it lands.

## Branches and PRs

- Never push to `main`. Every change goes on a branch and through a PR.
- Branch names: `pi/<topic>`, `gpu/<topic>`, `cloud/<topic>`, `viewer/<topic>`, `docs/<topic>`. Agent-created branches may use the agent's default name.
- One topic per PR. Say in the description what changed, how you checked it, and what is still simulated.
- The owner of the area merges. A PR that touches `docs/` or `shared/` needs the other person's approval first.
- Don't commit large files. Photos, datasets, model weights and 3D outputs over about 50 MB go in a GitHub release or a Google Drive link, and the PR or job request links to them.

## Talking to each other (Cotal)

The agents coordinate in Cotal. Sriram's Claude Code is `pipeline`; Tushar's Codex is `gpu-trainer`.

- Ask for GPU work in `#jobs` using [docs/templates/gpu-job-request.md](docs/templates/gpu-job-request.md). Reply in the same thread with the results link when done.
- **Cotal keeps only 7 days of history.** Anything decided in Cotal that matters after a week goes in [docs/decisions.md](docs/decisions.md) in a PR. The repo is the record, Cotal is the conversation.
- Before starting work, read `docs/decisions.md` and `docs/capture-format.md`.

## Standing rules

- Plan first and get the owner's OK before big builds, long reconstruction runs, downloads over 2 GB, or anything paid.
- Sparse dot clouds are not an acceptable view for farmers.
- Never fabricate health scores or accuracy figures. Report what was measured, against what, and how many samples.
