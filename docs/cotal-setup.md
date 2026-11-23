# Cotal setup

How Sriram's Claude Code and Tushar's Codex talk to each other on [Cotal Cloud](https://cotal.cloud). Each person signs up and connects their own agent; this file is what to paste. Button names in Cotal may differ slightly from the wording here.

## 1. Space

- **Name:** `GroundZero`
- **Members:** Sriram, Tushar (the free plan allows 3 people per space and keeps 7 days or 10 MiB of history).
- **Description** (paste):

  > GroundZero: center-pivot camera (Raspberry Pi 5) that captures and uploads crop photos; the cloud turns them into 3D field models and crop-health flags. Repo: https://github.com/sriramJ24/groundzero. The repo is the record; Cotal history lasts 7 days, so decisions go in docs/decisions.md.

## 2. Channels

| Channel | Purpose (paste as the channel description) |
|---|---|
| `#general` | Day-to-day coordination between Sriram, Tushar and their agents. Anything decided here that matters next week goes in docs/decisions.md. |
| `#jobs` | GPU job requests and results only. One job per message, using docs/templates/gpu-job-request.md. Reply in the job's thread. Big files as GitHub release or Drive links. |
| `#capture` | The Pi capture format and upload (docs/capture-format.md). Proposed changes go in a PR to that file. |

## 3. Agents and roles

| Role | Who | Agent | Machine |
|---|---|---|---|
| `pipeline` | Sriram | Claude Code | Sriram's laptop (CPU) |
| `gpu-trainer` | Tushar | Codex (Cotal's Codex connector is in beta) | Tushar's laptop (RTX 3070 Laptop GPU, 8 GB) |

**Role description for `pipeline`** (paste):

> Sriram's Claude Code. Owns cloud processing (pipelines/, backend/), the 3D viewer (viewer/) and the dashboard (frontend/) in sriramJ24/groundzero. Sends GPU work to gpu-trainer in #jobs using docs/templates/gpu-job-request.md. Follows CLAUDE.md. Works on branches and PRs only, never main.

**Role description for `gpu-trainer`** (paste):

> Tushar's Codex on his laptop (RTX 3070, 8 GB VRAM). Owns Pi capture and upload (pi/, hardware/) and GPU jobs: model training and photoreal 3D (gpu/) in sriramJ24/groundzero. Picks up requests in #jobs, replies in the same thread with a GPU JOB RESULT and a results link. Follows AGENTS.md. Works on branches and PRs only, never main.

## Connecting Claude Code as `pipeline`

From the Cotal docs (docs.cotal.ai/connect-claude), for a Claude Code session you open yourself:

1. Install the Cotal CLI: `curl -fsSL get.cotal.ai | sh` (or `npm install -g cotal-ai` with Node 22.10+).
2. `cotal login` (if it asks for an authority, use the one Cotal Cloud shows when you sign in), then `cotal space` and `cotal use <space>` to select the GroundZero space.
3. `cotal setup --configure-only` installs the Claude Code plugin.
4. Open Claude Code in the repo folder and ask it to call `cotal_connect` with the name `pipeline`.
5. Open the approval page it returns, check the space and permissions, and approve.
6. Ask it to call `cotal_orientation` to confirm it is in the GroundZero space.

The approval shares the session's activity from then on (messages, replies, tool calls), not earlier history.

## 4. First messages

Post in `#general` once both agents are connected (paste):

> Hi gpu-trainer, this is pipeline. Before starting anything, please read AGENTS.md, docs/decisions.md and docs/capture-format.md on main. I'll post a smoke-test job in #jobs next.

Pin in `#jobs` (paste):

> How to ask for GPU work: copy the GPU JOB REQUEST block from docs/templates/gpu-job-request.md, fill it in, post it as a new message here. gpu-trainer replies in the thread with GPU JOB RESULT. Inputs and outputs are links (GitHub release or Drive), not attachments. If a result changes a plan, add it to docs/decisions.md in the PR.

## 5. Each week

Cotal history expires after 7 days. Once a week, skim `#general` and `#capture` for anything decided and add it to `docs/decisions.md`.
