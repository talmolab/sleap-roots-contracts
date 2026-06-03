---
description: Comprehensive pre-merge verification workflow
---

# Pre-Merge Check

Comprehensive pre-merge verification for pull requests, including local CI, Copilot comment analysis, and test coverage.

## Purpose

This command performs a full pre-merge check by:

1. Running local CI checks (lint + tests)
2. Fetching and categorizing GitHub Copilot review comments
3. Verifying GitHub Actions CI status
4. Creating a prioritized action plan for remaining issues

## Step 1: Local CI Checks

Run CI-equivalent checks from `.github/workflows/ci.yml`:

```bash
# Lint: Black formatting check
uv run black --check src/sleap_roots_contracts tests

# Lint: Ruff linting
uv run ruff check src/sleap_roots_contracts

# Tests: Full test suite
uv run pytest tests/

# Coverage: Test coverage report (CI uses --cov-report=xml)
uv run pytest --cov=src/sleap_roots_contracts --cov-report=xml --cov-report=term-missing --durations=-1 tests/
```

If any check fails, fix the issue before proceeding.

## Step 2: Check GitHub CI Status

```bash
# Get current PR number
gh pr view --json number --jq .number

# Check CI status
gh pr checks
```

If CI is failing, investigate and fix before continuing.

## Step 3: Fetch Copilot Review Comments

```bash
# Get the PR number
PR_NUMBER=$(gh pr view --json number --jq .number)

# Get inline code review comments
gh api repos/talmolab/sleap-roots-contracts/pulls/$PR_NUMBER/comments --jq '.[] | {path: .path, line: .line, body: .body}'

# Get review summaries
gh api repos/talmolab/sleap-roots-contracts/pulls/$PR_NUMBER/reviews --jq '.[].body'
```

## Step 4: Categorize and Prioritize

Categorize all comments by priority:

- **CRITICAL**: Data consistency issues, incorrect statistical calculations, broken functionality, security vulnerabilities
- **HIGH**: Type safety violations, missing tests, significant bugs, code maintainability issues
- **MEDIUM**: Code quality issues, performance concerns, style inconsistencies
- **LOW**: Documentation improvements, minor refactoring, nice-to-haves
- **NO ACTION**: Working as designed, false positives, already fixed

## Step 5: Generate Action Plan

```
## Pre-Merge Analysis

### Summary
- Total comments: X
- Already fixed: Y
- Requiring action: Z

### CRITICAL Issues (Must Fix)
1. [file.py:line] Description
   - Impact: ...
   - Fix: ...

### HIGH Issues (Should Fix)
...

### MEDIUM Issues (Consider)
...

### LOW Issues (Optional)
...

### NO ACTION (Working as Designed)
...

## Recommended Action Plan

Phase 1 (Blocking): Fix CRITICAL issues → Run tests → Commit
Phase 2 (Pre-merge): Fix HIGH issues → Run tests → Commit
Phase 3 (Future work): Create issues for MEDIUM/LOW items
```

## Step 6: Execute Fixes

1. Implement CRITICAL and HIGH priority fixes immediately
2. Run tests after each fix
3. Commit changes with clear descriptions
4. Mark MEDIUM and LOW priority items for future work or accept as-is

## Step 7: Final Verification

After all fixes:

```bash
# Run full CI locally one more time
uv run black --check src/sleap_roots_contracts tests && uv run ruff check src/sleap_roots_contracts && uv run pytest tests/

# Verify GitHub CI passes
gh pr checks

# Check coverage
uv run pytest --cov=src/sleap_roots_contracts --cov-report=xml --cov-report=term-missing --durations=-1 tests/
```

## Integration

- `/lint` - Quick formatting and linting check
- `/coverage` - Detailed test coverage analysis
- `/review-pr` - Manual review of PR comments
- `/run-ci-locally` - Run exact CI checks locally
- `/update-changelog` - Update CHANGELOG before merge

## When to Use

- After receiving Copilot review comments
- Before requesting final review from maintainers
- Before merging to main
- After making significant changes to a PR
