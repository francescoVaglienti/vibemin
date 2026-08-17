---
name: vibemin
description: Minimize AI-authored code and test changes while preserving behavior, style, and test strength. Use after implementing or refactoring code, when a diff is larger than necessary, when tests contain verbose classes/fixtures/mocks, or when asked to simplify, reduce LOC, reduce complexity, condense tests, or keep a patch minimal.
---

# Vibemin

Prefer the smallest maintainable patch that proves the requested behavior. Do not optimize
for compressed syntax or line count alone.

## Minimize production changes

1. Read the diff and repository instructions.
2. Identify the narrowest focused test plus the repository's non-mutating lint, format-check,
   and typecheck commands.
3. Keep changed tests outside the path scope so passing checks cannot delete them.
4. Preview, review, then apply:

```sh
vibemin src/changed_area \
  --dry-run \
  --check "<focused test>" \
  --check "<lint/format/type check>"

vibemin src/changed_area \
  --check "<focused test>" \
  --check "<lint/format/type check>"
```

Never claim global minimality. Report the removed and retained diff units and the checks used.

## Refactor an existing test suite

First propose structure; `vibemin` only removes lines already present in the diff.

- Prefer flat, isolated test functions when no shared object state is required.
- Build files and payloads in memory.
- Keep one high-information golden-path test covering interacting output rules.
- Keep one additional test per independent failure mode or boundary.
- Remove framework behavior tests, private-helper tests, mock choreography, and cases already
  implied by a stronger test.
- Preserve readability: do not create dense one-liners merely to reduce LOC.

Before editing, record the passing suite and its mutation result. Coverage is only a fallback;
executing a line does not prove an assertion checks it.

### Preserve the same test cases

When simplifying fixtures or bodies without merging cases, preserve deterministic collection
output:

```sh
vibemin tests/area \
  --check "pytest -q tests/area" \
  --preserve-output "pytest --collect-only -q tests/area | sed '/collected in/d'"
```

### Condense or merge test cases

Do not preserve collection output when test IDs are intentionally changing. Require the same
killed-mutant set or an agreed mutation threshold instead:

```sh
vibemin tests/area \
  --check "pytest -q tests/area" \
  --check "<command that verifies the mutation baseline>"
```

Every retained test must catch a distinct plausible defect. Explain that defect in the review,
not necessarily as a comment in the code.

## Guardrails

- Never minimize test files with ordinary test success as the sole oracle.
- Never weaken assertions, remove boundary coverage, or lower mutation thresholds to pass.
- Never include mutating formatters in `--check`; use formatter check mode.
- Stop if the original candidate fails, checks are flaky, or required ignored files are absent
  from the disposable worktree.
- Review the resulting diff and rerun the full relevant suite in the real checkout.
