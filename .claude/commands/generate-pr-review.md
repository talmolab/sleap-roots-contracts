# Generate PR Review

Generate a structured, adversarial code review for a pull request using a team of
specialized subagents, then post it to GitHub as a PR review comment.

## Arguments

$ARGUMENTS

If a PR number is provided, use it directly. Otherwise detect from the current branch:

```bash
unset GITHUB_TOKEN && gh pr view --json number --jq .number
```

## Step 1: Gather PR Context

Collect everything the subagent team needs before launching:

```bash
# PR metadata (title, body, files changed, diff)
unset GITHUB_TOKEN && gh pr view <PR_NUMBER> --json title,body,headRefName,baseRefName

# List of files changed
unset GITHUB_TOKEN && gh pr diff <PR_NUMBER> --name-only

# Full diff (cap to reasonable size)
unset GITHUB_TOKEN && gh pr diff <PR_NUMBER>

# Existing Copilot/human review comments already posted
unset GITHUB_TOKEN && gh api repos/talmolab/sleap-roots-contracts/pulls/<PR_NUMBER>/reviews \
  --jq '.[] | {author: .user.login, state: .state, body: .body}'
unset GITHUB_TOKEN && gh api repos/talmolab/sleap-roots-contracts/pulls/<PR_NUMBER>/comments \
  --jq '.[] | {path: .path, line: .line, body: .body}'
```

Also read:
- `openspec/project.md` for project conventions
- Any OpenSpec change files related to this PR (`openspec/changes/<id>/`)

## Step 2: Launch 5 Specialized Subagents in Parallel

Launch ALL 5 subagents in a **single message** so they run concurrently. Embed the
full diff, file list, and PR description in each prompt — do not rely on summaries.
Each subagent MUST read the actual changed source files for context.

**Repo root:** `c:/repos/sleap-roots-contracts`

---

### Subagent 1: Code Quality

> Role: **Code Quality Reviewer**
>
> Be adversarial. Find real problems, not style nitpicks.
>
> Review the changed files for:
> - Correctness: does the logic do what it claims?
> - Error handling: are edge cases handled or silently ignored?
> - Dead code, unreachable branches, redundant operations
> - Variable naming that obscures intent
> - Functions doing more than one thing
> - Any introduced regressions visible from reading the diff
>
> Read the actual changed source files. Reference specific line numbers.
> Return: numbered issues with file:line, severity (BLOCKING/IMPORTANT/SUGGESTION),
> and a concrete suggested fix for each.

---

### Subagent 2: Testing & TDD

> Role: **Testing & TDD Reviewer**
>
> Be adversarial. Find gaps that would let bugs slip through CI.
>
> Review the test changes for:
> - TDD ordering: were tests written before or after the implementation?
> - Test specificity: do assertions actually catch the bug being fixed, or just
>   check that the code runs?
> - Missing scenarios from the spec or PR description not covered by tests
> - Tests that pass vacuously (e.g., asserting file exists rather than file content)
> - Missing edge cases (boundary values, empty inputs, missing columns)
> - Fixture dependencies that make tests brittle
>
> Read both the test files and the source files they test.
> Return: numbered issues with file:line, severity, and concrete suggested additions.

---

### Subagent 3: Scientific Rigor

> Role: **Scientific Rigor Reviewer**
>
> This is a scientific Python package for publication-grade plant root phenotyping.
> Be adversarial about anything that could affect the validity of published results.
>
> Review for:
> - **Reproducibility**: does the change produce bit-identical results across runs?
> - **Traceability**: are all data transformations recorded in pipeline outputs?
> - **Data integrity**: could any samples, traits, or metadata be silently dropped
>   or modified without being logged?
> - **Publication readiness**: would a methods section accurately describe what
>   the code does after this change?
> - **NaN/missing data handling**: is missing data handled consistently and documented?
>
> Return: numbered issues with severity and scientific impact, not just code impact.

---

### Subagent 4: Statistical Correctness

> Role: **Statistical Correctness Reviewer**
>
> Review any statistical, mathematical, or numerical operations in the diff for:
> - Correct formula implementation (means, variances, correlations, p-values)
> - Off-by-one errors in indices or thresholds
> - Floating point comparisons that should use tolerances
> - Division-by-zero risks in denominators
> - Incorrect assumptions about data distribution or independence
> - FDR/p-value adjustments applied in the wrong order or scope
> - Threshold logic (< vs <=, > vs >=) that could silently mis-classify samples
>
> If the PR has no statistical changes, note that and focus on numerical
> correctness of any arithmetic present.
>
> Return: numbered issues with severity and mathematical justification.

---

### Subagent 5: Reproducibility & Traceability

> Role: **Reproducibility & Traceability Reviewer**
>
> This package produces pipeline outputs used in scientific publications.
> Every removal, transformation, and parameter choice must be traceable.
>
> Review for:
> - **Output completeness**: are all pipeline output files written correctly?
>   Do CSV files have correct headers, row counts, and column schemas?
> - **Config traceability**: are pipeline configs saved alongside outputs?
> - **Removal tracking**: are removed samples/traits logged with reasons?
> - **Schema consistency**: do output file schemas match what downstream steps expect?
> - **Version traceability**: is the code version recorded in outputs?
> - **Idempotency**: does running the pipeline twice produce identical outputs?
>
> Read the pipeline step files and any output-writing code touched by the diff.
> Return: numbered issues with severity and traceability impact.

---

## Step 3: Synthesize Into a Unified Review

After ALL 5 subagents return:

1. **Deduplicate** findings that appear in multiple reviews
2. **Categorize** each unique finding:
   - **Blocking** — Must fix before merge (incorrect behavior, broken output,
     data loss, failing tests, statistical errors)
   - **Important** — Should fix before merge (missing edge cases, incomplete
     traceability, unclear logic)
   - **Suggestion** — Optional improvement (style, minor clarity, future work)
3. **Write the review body** in this exact format:

```markdown
## Review Summary

[2-3 sentences: overall assessment, what the PR does, whether it's ready to merge]

## Blocking Issues

### 1. [Short title] — [file.py:line]
[Explanation of what's wrong and why it matters]
**Fix:** [Concrete suggestion]

### 2. ...

## Important Issues

### 1. [Short title] — [file.py:line]
[Explanation]
**Suggestion:** [Concrete suggestion]

### 2. ...

## Suggestions

- [Short bullet with file:line if applicable]
- ...

---
*Review by Claude Code subagent team (Code Quality · Testing/TDD · Scientific Rigor · Statistical Correctness · Reproducibility & Traceability)*
```

If there are **no blocking issues**, lead the summary with that clearly.

## Step 4: Post the Review

```bash
unset GITHUB_TOKEN && gh pr review <PR_NUMBER> --comment --body "<REVIEW_BODY>"
```

Then print the review body to the conversation so the user can read it.

## Notes

- Use `--comment` not `--approve` — you cannot approve your own PR on GitHub
- Always `unset GITHUB_TOKEN` before `gh` commands in this repo
- If the diff is very large (>500 lines), focus subagents on the most impactful
  changed files rather than exhaustive line-by-line coverage
- Do not rubber-stamp. If you find nothing wrong, say so explicitly with reasoning.
