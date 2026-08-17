# vibemin

`vibemin` removes unnecessary lines from an AI-generated Git diff while keeping the
behavior and style checks you choose green. It is a local, deterministic complement to
vibe coding: tests define what must be preserved, and delta debugging finds a smaller patch.

It never sends code anywhere. Candidate patches run in a temporary detached Git worktree;
the real checkout is updated only after a verified minimum has been found.

## Install

```sh
cd vibemin
uv tool install .
```

Install the user-wide Claude Code skill, standing instruction, and man page:

```sh
./scripts/install-user.sh
```

The installer adds `~/.claude/skills/vibemin/SKILL.md`, a short imported directive to
`~/.claude/CLAUDE.md`, and `~/.local/share/man/man1/vibemin.1`. If the latter is not on
your platform's default man path, use `man -M ~/.local/share/man vibemin`.

For development:

```sh
uv run --with pytest pytest
```

## Use

Run it in the Git repository containing the AI changes:

```sh
vibemin \
  --check "npm test -- --run" \
  --check "npm run lint" \
  --check "npm run typecheck" \
  --final-check "npm ci --ignore-scripts --dry-run"
```

Or minimize only a portion of the diff:

```sh
vibemin src/new-feature \
  --check "npm test -- --run tests/new-feature.test.ts" \
  --check "npm run lint"
```

Minimize an entire feature branch, including changes already committed on it, from the point
where it diverged from the target branch:

```sh
vibemin --feature-base origin/main \
  --check "pytest -q" \
  --check "npm run typecheck"
```

The result is written as working-tree changes on top of the current feature, ready to review
and amend or squash. `--base REF` remains available for an exact baseline; `--feature-base`
uses `git merge-base HEAD REF` so unrelated target-branch history is not included.

Preview the result without changing the checkout:

```sh
vibemin --dry-run --check "pytest -q" --check "ruff check ."
```

Preserve a deterministic contract snapshot while reducing code:

```sh
vibemin src \
  --check "pytest -q" \
  --preserve-output "pytest --collect-only -q | sed '/collected in/d'"
```

Each `--check` command is run from the root of the temporary worktree. Checks must be
non-mutating and should cover the behavior the patch is meant to add. Put the fastest,
most focused test first. Add the repository's formatter-in-check-mode, linter, and type
checker to keep accepted lines consistent with local style.

`--preserve-output` commands must exit successfully and produce deterministic output. The
first verified candidate establishes the snapshot; every smaller candidate must produce
the exact same stdout and stderr. This can preserve collected test IDs, an OpenAPI schema,
or another observable contract that an ordinary pass/fail check would not protect.

## Safe defaults

Ordinary green tests do not prove that tests themselves, dependency metadata, or rendered
visuals survived reduction. Vibemin therefore keeps these changes as fixed context by default:

- tests, specs, and snapshots;
- dependency manifests and generated lockfiles;
- stylesheets, fonts, icons, and raster/vector images.

The result reports every protected file. Unlock a category only with its matching oracle:

```sh
# Consolidating tests requires mutation testing or an equivalent strength check.
vibemin tests --reduce-tests \
  --check "pytest -q" \
  --test-strength-check "./scripts/check-mutation-baseline"

# A visual file requires a deterministic screenshot/DOM snapshot hash.
vibemin web/src --allow-visual-changes \
  --check "npm run build" \
  --preserve-output "./scripts/render-reference-screenshot --hash"

# Dependency files require consistency validation on every candidate.
vibemin pyproject.toml poetry.lock --allow-dependency-changes \
  --check "pytest -q" \
  --dependency-check "poetry check --lock"
```

Changed TypeScript requires a direct `tsc`/typecheck command or a package script that invokes
one. Auth, tenant, permission, token, cookie, session, or secret-related changes require an
explicit `--security-check`. Use `--final-check` for expensive clean-install, dependency-audit,
or broad integration validation that only needs to run once on the chosen result.

These rules prevent the two most misleading reductions: deleting assertions until tests pass
and deleting CSS until a non-visual production build passes.

## Minimizing tests safely

Never minimize tests with a passing test suite as the only check: deleting a test makes
the suite easier to pass. First refactor tests toward flat, isolated functions and compact
in-memory builders.

When simplifying test bodies without merging test cases, preserve the collected inventory:

```sh
vibemin tests \
  --reduce-tests \
  --check "pytest -q" \
  --preserve-output "pytest --collect-only -q | sed '/collected in/d'"
```

When intentionally merging or removing overlapping cases, collection output must change.
Use the same mutation score or killed-mutant set as the constraint instead:

```sh
vibemin tests \
  --reduce-tests \
  --check "pytest -q" \
  --test-strength-check "./scripts/check-mutation-baseline"
```

Collection preservation prevents accidental disappearance; only mutation testing protects
assertion strength while allowing deliberate consolidation. Coverage alone does not.

## What it minimizes

The baseline is `HEAD` by default. For text files, every inserted and deleted line is a
removable unit. Binary files and empty-file changes are atomic. Untracked, non-ignored
files are included. Files outside explicit path arguments remain present as fixed context.

The reducer repeatedly removes groups of units and retains a smaller candidate only when
all checks pass. The result is *1-minimal*: no remaining individual unit was shown to be
removable by the supplied checks. This is not a proof that the implementation is globally
shortest, and weak tests can permit incorrect removal.

## Guardrails and limitations

- Staged changes are rejected so the index and working tree cannot diverge unexpectedly.
- Tests, dependency metadata, and visual files are protected unless explicitly unlocked with
  an appropriate oracle.
- TypeScript is not reduced without typechecking, and security-sensitive code is not reduced
  without a security-specific check.
- Symlinks and changed directories/submodules are currently rejected.
- Ignored local files such as `.env`, `.venv`, and `node_modules` are not copied into the
  temporary worktree. Prefer checks whose dependencies are globally available, or commands
  that use a shared package-manager cache.
- Use `--base <ref>` for an exact baseline or `--feature-base <target-ref>` for the complete
  current feature since its merge-base with the target.
- Use `--max-attempts` and `--timeout` to bound cost.

Always review the final diff. `vibemin` knows only what the checks prove.
