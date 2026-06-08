---
description: Start a new feature — branch, OpenSpec proposal, then the TDD loop
---

# New Feature

Kick off a new feature in this repo following the lab's spec-driven + TDD workflow. Use this
as the single entry point so every feature starts the same way.

## Steps

1. **Clarify scope.** Restate the feature in one sentence. If it's ambiguous or spans multiple
   capabilities, stop and clarify before scaffolding anything.

2. **Branch off main.**
   ```bash
   git checkout main && git pull && git checkout -b <kebab-feature-name>
   ```

3. **Write the OpenSpec proposal.** Run `/openspec:proposal` to scaffold
   `openspec/changes/<feature>/` with `proposal.md` (why + what), `tasks.md` (the task
   breakdown), and `specs/<capability>/spec.md` (the capability requirements). Then validate:
   ```bash
   openspec validate <feature> --strict
   ```

4. **Review the proposal.** Run `/review-openspec` to have the proposal critically reviewed by a
   team of specialized subagents. Fix any blocking findings and re-run until the verdict is clear,
   then respect the approval gate — do not start implementing until the proposal is approved.

5. **Plan the work.** For small changes, `tasks.md` is the plan. For larger ones, expand each
   task into bite-sized TDD steps (one failing test → minimal code → commit).

6. **Implement task-by-task with `/tdd`.** Red → green → refactor → commit, one task at a time.
   Keep `tasks.md` in sync as you go via `/openspec:apply`.

7. **Pre-merge.** Run `/pre-merge-check` (black + ruff + full pytest + coverage). Regenerate
   `schema/*.json` and confirm the drift guard is green. Then `/pr-description` and open the PR.

8. **Archive after merge.** Run `/openspec:archive <feature>` to fold the change into the specs.

## Conventions (this repo)

- Pure, dependency-light, Bloom-agnostic library — **no DB / network / Argo / model code**
  (see `openspec/project.md`).
- **Pydantic is canonical**; `schema/*.json` is generated and drift-guarded. Never hand-edit
  the emitted schema — change the models and regenerate.
- Hashes are producer-side only; Bloom treats them as opaque.
