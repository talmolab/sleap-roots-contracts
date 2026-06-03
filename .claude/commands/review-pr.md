# Review GitHub PR Comments

Review and address GitHub Copilot or human review comments on pull requests.

## Arguments

$ARGUMENTS

If a PR number is provided as an argument, use it directly. Otherwise, detect from the current branch:

```bash
gh pr view --json number --jq .number
```

## Step 1: Fetch PR Comments

```bash
# View PR with comments
gh pr view <PR_NUMBER> --comments

# Get inline code review comments with file paths and line numbers
gh api repos/talmolab/sleap-roots-contracts/pulls/<PR_NUMBER>/comments --jq '.[] | {path: .path, line: .line, body: .body}'

# Get review summaries
gh api repos/talmolab/sleap-roots-contracts/pulls/<PR_NUMBER>/reviews --jq '.[].body'
```

## Step 2: Categorize Comments

Organize comments by priority:

### Critical (Must Fix)
- Data consistency issues
- Broken functionality
- Security issues
- Incorrect statistical calculations

### Important (Should Fix)
- API inconsistencies
- Missing or incorrect tests
- Type safety violations
- Code maintainability issues
- Misleading documentation

### Nice to Have (Consider)
- Code quality improvements
- Style improvements
- Performance optimizations (unless critical)
- Additional features
- Documentation enhancements

## Step 3: Create Action Plan

1. **List all comments** with their locations (file:line)
2. **Prioritize** by severity (Critical > Important > Nice to Have)
3. **Group related changes** (e.g., all import fixes together)
4. **Identify already-fixed** issues from previous commits
5. **Test after each group** of changes
6. **Document decisions** if not implementing a suggestion

## Step 4: Implement Fixes

1. Fix Critical issues first, run tests, commit
2. Fix Important issues, run tests, commit
3. Consider Nice to Have items - implement or note for future

## Step 5: Respond to Review

After addressing comments:

```bash
# Post a comment summarizing changes
gh pr comment <PR_NUMBER> --body "Addressed review comments:
- Fixed [summary of critical fixes]
- Updated [summary of important fixes]
- Noted [items deferred to future work]
"
```

## Integration

- Run `/lint` after fixes to verify code style
- Run `/coverage` to check test coverage after adding tests
- Run `/run-ci-locally` to verify full CI passes
- Use `/pre-merge-check` for comprehensive pre-merge verification
