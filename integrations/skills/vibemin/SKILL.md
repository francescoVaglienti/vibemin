---
name: vibemin
description: Minimize AI-authored code and test changes while preserving behavior, style, and test strength. Use after implementing or refactoring code, when a diff is larger than necessary, when tests contain verbose classes/fixtures/mocks, or when asked to simplify, reduce LOC, reduce complexity, condense tests, or keep a patch minimal.
---

# Vibemin

Prefer the smallest maintainable patch that proves the requested behavior. Do not optimize
for compressed syntax or line count alone.

## Minimize production changes

1. Read the diff and repository instructions.
2. Before reduction, consolidate AI-authored tests deliberately into the minimum integration
   suite: one high-information golden path plus one case per independent security or failure
   boundary. Do this by review, not by letting a passing suite delete its own assertions.
3. Perform a security pass over authentication, authorization, tenant isolation, secrets,
   caching, input limits, logging, and dependencies. Add the resulting focused integration
   checks before minimization.
4. Identify the narrowest focused test plus the repository's non-mutating lint, format-check,
   strict typecheck, and security commands.
5. Leave tests, manifests/lockfiles, and visual files protected. Validate lock consistency and
   clean installation once with `--final-check`; do not spend every candidate on unchanged
   generated files.
6. Preview, review, then apply:

```sh
vibemin src/changed_area \
  --dry-run \
  --check "<focused test>" \
  --check "<lint/format/strict type check>" \
  --security-check "<focused security check>" \
  --final-check "<lock consistency or clean-install check>"

vibemin src/changed_area \
  --check "<focused test>" \
  --check "<lint/format/strict type check>" \
  --security-check "<focused security check>" \
  --final-check "<lock consistency or clean-install check>"
```

For a feature spanning several commits, use `--feature-base origin/main`. Vibemin reduces the
complete diff since the merge-base and leaves the result as working-tree changes to review
before amending or squashing the feature.

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
  --reduce-tests \
  --check "pytest -q tests/area" \
  --preserve-output "pytest --collect-only -q tests/area | sed '/collected in/d'"
```

### Condense or merge test cases

Do not preserve collection output when test IDs are intentionally changing. Require the same
killed-mutant set or an agreed mutation threshold instead:

```sh
vibemin tests/area \
  --reduce-tests \
  --check "pytest -q tests/area" \
  --test-strength-check "<command that verifies the mutation baseline>"
```

Every retained test must catch a distinct plausible defect. Explain that defect in the review,
not necessarily as a comment in the code.

## Guardrails

- Never minimize test files with ordinary test success as the sole oracle.
- Never minimize manifests or lockfiles merely because an existing environment still runs.
- Never minimize CSS or visual assets without deterministic screenshot/DOM preservation.
- Never relax or omit strict TypeScript checks to obtain a smaller diff.
- Require a separate security oracle for auth, tenant, session, token, or secret changes.
- Never weaken assertions, remove boundary coverage, or lower mutation thresholds to pass.
- Never include mutating formatters in `--check`; use formatter check mode.
- Stop if the original candidate fails, checks are flaky, or required ignored files are absent
  from the disposable worktree.
- Review the resulting diff and rerun the full relevant suite in the real checkout.
