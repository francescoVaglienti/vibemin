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
  --check "npm run typecheck"
```

Or minimize only a portion of the diff:

```sh
vibemin src/new-feature \
  --check "npm test -- --run tests/new-feature.test.ts" \
  --check "npm run lint"
```

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

## Minimizing tests safely

Never minimize tests with a passing test suite as the only check: deleting a test makes
the suite easier to pass. First refactor tests toward flat, isolated functions and compact
in-memory builders.

When simplifying test bodies without merging test cases, preserve the collected inventory:

```sh
vibemin tests \
  --check "pytest -q" \
  --preserve-output "pytest --collect-only -q | sed '/collected in/d'"
```

When intentionally merging or removing overlapping cases, collection output must change.
Use the same mutation score or killed-mutant set as the constraint instead:

```sh
vibemin tests \
  --check "pytest -q" \
  --check "./scripts/check-mutation-baseline"
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
- Symlinks and changed directories/submodules are currently rejected.
- Ignored local files such as `.env`, `.venv`, and `node_modules` are not copied into the
  temporary worktree. Prefer checks whose dependencies are globally available, or commands
  that use a shared package-manager cache.
- Use `--base <commit>` to compare against something other than `HEAD`.
- Use `--max-attempts` and `--timeout` to bound cost.

Always review the final diff. `vibemin` knows only what the checks prove.
