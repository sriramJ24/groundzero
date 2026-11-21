# GPU job request (Cotal `#jobs`)

Copy the block below into a new message in Cotal `#jobs`. One job per message. The GPU side (`gpu-trainer`) replies in the same thread.

Big inputs and outputs are **links**, not attachments: a GitHub release asset on this repo, or a Google Drive link the other person can open. Cotal history lasts 7 days, so when a job finishes, the results link and anything decided also go into the PR or into [docs/decisions.md](../decisions.md).

## Request

```
GPU JOB REQUEST
Job: <short name, e.g. "splat section-3 day040">
From: <pipeline | gpu-trainer>
Branch: <branch to check out, e.g. gpu/splat-section3>
Commit: <commit hash, so the run is reproducible>

What to run:
<command or script and its arguments, e.g. python gpu/splat/train.py --config gpu/splat/configs/section3.yaml>

Inputs:
- <name>: <GitHub release or Drive link> (<size>, <sha256 if large>)

Expected outputs:
- <file or folder>: <what it is, format, where it should go, e.g. viewer/field3d/splat/section_splat.json>
- <metrics to report, e.g. PSNR on held-out views, training time, GPU used>

Done when:
<the check that says it worked, e.g. "loads in the viewer's Photoreal view without errors">

Limits:
<max run time, max GPU memory, anything not to do, e.g. "stop after 2 h">

Results link: <filled in by gpu-trainer>
```

## Reply when done

```
GPU JOB RESULT
Job: <same name>
Status: <done | failed | partial>
Branch / PR: <link>
Results: <GitHub release or Drive link>
Metrics: <what was measured, against what, how many samples>
Run: <GPU, time taken, commit hash>
Notes: <anything that went wrong or should be decided>
```

If the result changes a plan or a format, add an entry to `docs/decisions.md` in the same PR.
