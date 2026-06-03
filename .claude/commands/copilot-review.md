# View GitHub Copilot Review Comments

View GitHub Copilot's inline code-review comments (and review summaries) for a PR, so they
can be addressed before merge. Part of the pre-merge review step.

## Current PR (repo-agnostic, recommended)

Inline comments on the current branch's PR:
```bash
gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/$(gh pr view --json number -q .number)/comments \
  --jq '.[] | select(.user.login | contains("opilot")) | "File: \(.path):\(.line // .original_line)\n\(.body)\n" + ("="*80)'
```

## Specific PR (GraphQL — summaries + inline comments in one call)

```bash
gh api graphql -f query='
query($owner:String!, $name:String!, $pr:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$pr) {
      reviews(first: 20) {
        nodes {
          author { login }
          state
          body
          submittedAt
          comments(first: 100) { nodes { path line body } }
        }
      }
    }
  }
}' -F owner="$(gh repo view --json owner -q .owner.login)" \
   -F name="$(gh repo view --json name -q .name)" \
   -F pr=PR_NUMBER \
  --jq '.data.repository.pullRequest.reviews.nodes[]
        | select(.author.login | contains("opilot"))
        | "[\(.state)] \(.submittedAt)\n\(.body)\n" + (.comments.nodes[] | "File: \(.path):\(.line)\n\(.body)\n") + ("="*80)'
```

## Notes

- Copilot **inline** comments come from user `Copilot`; **review summaries** come from
  `copilot-pull-request-reviewer[bot]`. `contains("opilot")` matches both.
- Run this as part of pre-merge review (alongside `/review-pr` and `/pre-merge-check`) so all
  Copilot feedback is triaged before merging. Evaluate each suggestion on its merits — apply the
  good ones, and note why if you decline (see superpowers:receiving-code-review).
