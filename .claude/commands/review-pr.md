---
description: Adversarial multi-subagent code review of a PR or a local branch diff
---

# Review PR — Subagent Team

Launch a team of parallel, adversarial review subagents against a change, synthesize their
findings, and either post a review (PR mode) or report locally (pre-PR mode). Each subagent is
instructed to find real problems, not rubber-stamp.

## Arguments

`$ARGUMENTS` is either a **PR number** (review an open PR) or a **branch name / empty**
(pre-PR self-review of the local diff). Detect the mode:

```bash
# PR mode if $ARGUMENTS is a number AND that PR exists; else local mode.
if [[ "$ARGUMENTS" =~ ^[0-9]+$ ]] && gh pr view "$ARGUMENTS" >/dev/null 2>&1; then
  MODE=pr; PR="$ARGUMENTS"
else
  MODE=local
fi
```

## Step 1: Gather context

**PR mode:**
```bash
gh pr view "$PR" --json title,body,baseRefName,headRefName,author,files
gh pr diff "$PR"
gh pr checks "$PR"
# existing Copilot comments (already addressed?) — see /copilot-review
```

**Local mode** (no PR yet — review the branch against main):
```bash
git fetch origin main -q
git diff "$(git merge-base origin/main HEAD)"..HEAD     # the full change
git log --oneline "$(git merge-base origin/main HEAD)"..HEAD
```

Also read the OpenSpec change linked to this work (`openspec/changes/<id>/`) and
**`openspec/project.md`** for repo-specific values to review against.

## Step 2: Launch the subagent team (parallel, single message)

Embed the full diff + description + CI status (PR mode) into each prompt. Run **all** lenses in
one message so they execute in parallel. Each returns BLOCKING / IMPORTANT / SUGGESTION findings.

- **Lens 1 — Correctness & contract fidelity.** Does the code do what the PR/spec claims? Trace
  the logic. For this repo specifically (from `project.md`): provenance/traceability is preserved;
  hashes are deterministic and producer-side only; idempotency holds; **no DB / network / Argo /
  model code** leaks in; the emitted `schema/*.json` matches the models (drift guard).
- **Lens 2 — Testing & TDD.** Were tests written first? Right level? Specific assertions (not
  "works")? Missing edge cases (empty, `None`, NaN/inf, boundary)? 1:1 mapping between spec
  scenarios and tests? Do existing tests break?
- **Lens 3 — API design & code quality.** Clear public API and naming; full type hints; google
  docstrings; no dead code; suppressions (`# noqa`, `# type: ignore`) justified; ripple effects
  in unchanged files.
- **Lens 4 — Edge cases & failure modes.** Adversarial inputs; does it degrade defensibly
  (NaN→None, empty→empty, not crashes)? Statelessness / purity where expected? Cross-language
  serialization round-trips (Pydantic ↔ JSON ↔ schema)?

(Read `project.md`; if the repo has domain concerns beyond these, add a lens for them.)

## Step 3: Synthesize

Deduplicate; prioritize **BLOCKING** (must fix) > **IMPORTANT** (should fix) > **SUGGESTION**.
Verdict: `REQUEST_CHANGES` if any BLOCKING, else `COMMENT` if IMPORTANT items, else `APPROVE`.

## Step 4: Output

**Local mode (pre-PR):** print the synthesized review to the user. Do **not** post anything to
GitHub. If BLOCKING/IMPORTANT findings exist, fix them before opening the PR.

**PR mode:** post to the PR. GitHub forbids approving/requesting-changes on your own PR, so
detect that first and fall back to a comment:
```bash
PR_AUTHOR=$(gh pr view "$PR" --json author --jq .author.login)
GH_USER=$(gh api user --jq .login)
if [ "$PR_AUTHOR" = "$GH_USER" ]; then
  gh pr review "$PR" --comment -b "> **Verdict: <VERDICT>** (own PR → comment)

<BODY>"
else
  gh pr review "$PR" --approve -b "<BODY>"          # or --request-changes / --comment
fi
```

## Integration
Used by `/pre-merge-check` (Phase 3.5 pre-PR self-review in **local mode**, and Phase 6
post-PR in **PR mode**). Pair with `/copilot-review` to fetch Copilot's comments. Evaluate each
finding on its merits — see superpowers:receiving-code-review.
