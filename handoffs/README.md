# Handoffs

How Sriram's Claude Code and Tushar's Codex pass work to each other. A handoff is one markdown file in this folder. It goes back and forth through normal PRs, so the repo keeps the full history and nothing expires.

## The loop

1. **Ask.** Copy [TEMPLATE.md](TEMPLATE.md) to `handoffs/YYYY-MM-DD-<short-name>.md` on a new branch off `main` (`handoff/<short-name>`). Fill in the Request section, set `Status: open`, and open a PR titled `Handoff: <short-name>`. Send the other person the PR link.
2. **Pick it up.** The person it's addressed to reads it and merges the PR. Merging means "got it, working on it". If something is unclear, comment on the PR instead of merging.
3. **Do the work** on your own branch, in your own folders (see `CLAUDE.md` / `AGENTS.md`).
4. **Answer.** In the same handoff file, fill in the Result section and change `Status` to `done`, `failed` or `blocked`. Open a PR titled `Handoff result: <short-name>` with the file change plus any code. Send the other person the PR link.
5. **Close.** The person who asked reads the result and merges it (or the code owner merges, if the PR also changes code). If the result changes a plan or a format, add an entry to `docs/decisions.md` in that PR.

## Rules

- One job per file. Never reuse a file for a new job; make a new one.
- A PR that only changes files in `handoffs/` needs no extra approval beyond the step above.
- Big inputs and outputs (over about 50 MB) are links: a GitHub release on this repo or a Google Drive link. Never commit them.
- Report what was measured, against what, and how many samples. If something wasn't measured, write "not measured".
- Anything that costs money, downloads more than 2 GB or runs for hours needs the owner's OK first, in the request.

## Starting a session

Agents: at the start of every session, `git pull` on `main` and run

```
grep -l "Status: open" handoffs/*.md
```

Then open any file whose `To:` line names your person (Sriram or Tushar). Those are waiting on you.

## Status values

| Status | Meaning |
|---|---|
| `open` | Waiting for the person it's addressed to |
| `done` | Finished; Result section filled in |
| `failed` | Tried and didn't work; Result says why |
| `blocked` | Needs an answer from the person who asked; Result says what |
