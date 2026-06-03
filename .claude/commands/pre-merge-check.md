---
description: Comprehensive pre-merge verification workflow
---

# Pre-Merge Check

Full pre-merge verification: local CI, a pre-PR subagent self-review, OpenSpec + schema
checks, PR creation, and Copilot-comment triage. Run before opening a PR and before merging.

## Phase 1: Code quality

```bash
uv run black --check src tests
uv run ruff check src tests
```
If either fails, fix with `/fix-formatting`, then re-run.

## Phase 2: Tests, coverage, schema, OpenSpec

```bash
uv run pytest --cov=src/sleap_roots_contracts --cov-report=term-missing tests/

# Schema drift guard (regenerate must equal committed)
uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/

# If an OpenSpec change is in flight:
openspec list
openspec validate <change-id> --strict
```

## Phase 3: Documentation

- Docstrings current for all changed code (google convention).
- README updated if the public API changed.
- OpenSpec tasks checked off (`openspec list`).

## Phase 3.5: Pre-PR self-review (do this BEFORE creating the PR)

Run `/review-pr` on the **local branch diff** (pass the branch name, not a PR number — the PR
doesn't exist yet). This launches the critical-review subagent team against the change the
same way they'd review an external PR.

**Rationale:** Copilot reliably flags exactly what this team would catch (e.g. a test that
bypasses the path it was meant to regression-test). Running our own review pre-PR fixes those
in one iteration instead of two, and avoids burning a Copilot review cycle. If any BLOCKING /
IMPORTANT findings come back, fix them and restart from Phase 1.

## Phase 4: Create / update the PR

```bash
gh pr create --title "<title>" --body "<summary, test results, OpenSpec link if any>"
```

## Phase 5: CI monitoring

```bash
gh pr checks
```
CI runs lint + the schema drift guard + pytest on Ubuntu (Python 3.11 / 3.12). Investigate any
failure before proceeding.

## Phase 6: Copilot + review feedback triage

Fetch Copilot's comments with `/copilot-review`, then categorize:

- **CRITICAL** — broken functionality, incorrect results, data/contract inconsistencies, security
- **HIGH** — type-safety violations, missing tests, real bugs, maintainability
- **MEDIUM** — code quality, performance, style
- **LOW** — docs, minor refactors, nice-to-haves
- **NO ACTION** — working as designed / false positive / already fixed

Fix CRITICAL + HIGH now (re-run tests after each); file issues for MEDIUM/LOW. Evaluate each
suggestion on its merits and note why if you decline (see superpowers:receiving-code-review).

## Phase 7: Changelog

Run `/update-changelog` to add a `[Unreleased]` entry. (If `docs/CHANGELOG.md` doesn't exist
yet, create it in Keep-a-Changelog format first.)

## Phase 8: Final verification

```bash
uv run black --check src tests && uv run ruff check src tests
uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/
uv run pytest tests/
git push
gh pr checks
git fetch origin main && git merge-base --is-ancestor origin/main HEAD   # branch up to date with main
```

## Output

```markdown
# Pre-Merge Check Results
## Code Quality:  [x] black  [x] ruff
## Tests:         [x] pytest (X passed)  [x] coverage  [x] schema drift guard
## OpenSpec:      [x] validated (or N/A)
## Self-review:   [x] /review-pr clean (or findings fixed)
## PR:            [x] #X created, checks green
## Copilot:       [x] CRITICAL/HIGH addressed; MEDIUM/LOW filed
## Changelog:     [x] entry added (or N/A)
## Status: READY TO MERGE
```

## Integration
`/lint` · `/fix-formatting` · `/coverage` · `/run-ci-locally` · `/review-pr` · `/copilot-review`
· `/update-changelog`
