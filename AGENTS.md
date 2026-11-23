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
| Pi capture and upload | Tushar (TMRmehta) | Codex | `pi/`, `hardware/` (older ESP32 work) |
| GPU jobs: model training, photoreal 3D (splats) | Tushar | Codex | `gpu/` |
| Cloud processing | Sriram (sriramJ24) | Claude Code | `pipelines/`, `backend/` |
| 3D viewer and dashboard | Sriram | Claude Code | `viewer/`, `frontend/` |
| Shared contracts and decisions | Both | Both | `docs/`, `shared/` |

Rules:

- Work only in your own folders. If you need a change in someone else's folder, ask in a handoff (see `handoffs/`) or open an issue; don't edit it.
- `docs/` and `shared/` are shared. A change there needs a PR that the other person approves.
- Create `pi/` or `gpu/` when the first code for it lands.

## Branches and PRs

- Never push to `main`. Every change goes on a branch and through a PR.
- Branch names: `pi/<topic>`, `gpu/<topic>`, `cloud/<topic>`, `viewer/<topic>`, `docs/<topic>`, `handoff/<name>`. Agent-created branches may use the agent's default name.
- One topic per PR. Say in the description what changed, how you checked it, and what is still simulated.
- The owner of the area merges. A PR that touches `docs/` or `shared/` needs the other person's approval first.
- Don't commit large files. Photos, datasets, model weights and 3D outputs over about 50 MB go in a GitHub release or a Google Drive link, and the PR or handoff links to them.

## Passing work to each other (handoff files)

Sriram's Claude Code and Tushar's Codex pass work through handoff files in [handoffs/](handoffs/README.md), sent through normal PRs. The repo is the record.

- To ask the other side for something (GPU work, a Pi change, a question that blocks you), copy [handoffs/TEMPLATE.md](handoffs/TEMPLATE.md) to a new file and open a PR, as `handoffs/README.md` describes.
- At the start of every session, `git pull` on `main` and check `handoffs/` for files with `Status: open` addressed to your person. Those are waiting on you.
- When you finish, fill in the Result section of that same file and open a PR. Put anything decided that matters later in [docs/decisions.md](docs/decisions.md) in the same PR.
- Before starting work, read `docs/decisions.md` and `docs/capture-format.md`.

## Standing rules

- Plan first and get the owner's OK before big builds, long reconstruction runs, downloads over 2 GB, or anything paid.
- Sparse dot clouds are not an acceptable view for farmers.
- Never fabricate health scores or accuracy figures. Report what was measured, against what, and how many samples.
