<div align="center">
  <img src="assets/vibemin-hero.svg" alt="Vibemin — make every line earn its place" width="100%">
</div>

<div align="center">

[![CI](https://github.com/francescoVaglienti/vibemin/actions/workflows/ci.yml/badge.svg)](https://github.com/francescoVaglienti/vibemin/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/francescoVaglienti/vibemin?color=6D5EF5)](https://github.com/francescoVaglienti/vibemin/releases/latest)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero runtime dependencies](https://img.shields.io/badge/runtime_dependencies-0-6D5EF5)](pyproject.toml)
[![MIT](https://img.shields.io/badge/license-MIT-0F766E)](LICENSE)

**Test-guided minimization for AI-generated Git diffs.**

Vibemin removes code your checks cannot justify—and keeps the patch that survives.

Works with **Claude Code**, **Codex**, **GitHub Copilot**, and **Gemini CLI**—or with no
AI agent at all.

[Quick start](#quick-start) · [How it works](#how-it-works) · [Safety model](#safety-model) · [Agents](#use-it-with-your-coding-agent)

</div>

---

AI coding tools are very good at adding code. They are less disciplined about taking it
back out. Vibemin treats your Git diff as a search space and your tests as a contract,
repeatedly removing candidate lines until every remaining unit has earned its place.

> Tests are the contract. The diff is negotiable.

```console
$ vibemin --feature-base origin/main \
    --check "pytest -q" \
    --check "ruff check ."

[001] PASS  retained=11844  1.42s
[027] fail  retained=10320  1.31s
[149] PASS  retained=9620   1.26s

Removed 2,224 of 11,844 diff units in 149 checks; 9,620 remain.
```

Vibemin runs locally in a disposable Git worktree. It never sends your code anywhere,
and it only updates the real checkout after the result has passed every required check.

## Quick start

### Install the CLI

Install the checksummed standalone binary on macOS or Linux. No Python is required:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-binary.sh | sh
```

Self-contained executables are published for macOS, Linux, and Windows on the
[Releases page](https://github.com/francescoVaglienti/vibemin/releases/latest). Git is the
only runtime prerequisite.

### Install the CLI and Agent Skill

This one-liner installs the binary, detects Claude Code, Codex, GitHub Copilot, and Gemini
CLI, and adds the Vibemin skill to the agents it finds:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh
```

One detected agent is selected automatically. Because a curl pipe is non-interactive,
multiple detected agents receive the skill together. Pin the destination when you only want
one host:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh -s -- --agent codex
```

Use `claude`, `codex`, `copilot`, `gemini`, `all`, or `standalone`. The skill teaches the
agent how to choose checks, protect tests and lockfiles, handle security-sensitive changes,
and minimize a complete feature rather than only the last uncommitted edit.

### Make Vibemin part of feature completion

Skills are selected when relevant; project instructions make the desired timing explicit.
Add the following block to the instruction file used by your agent:

| Agent | Project instruction file |
| --- | --- |
| Claude Code | [`CLAUDE.md`](https://code.claude.com/docs/en/memory#claudemd-files) |
| Codex | [`AGENTS.md`](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| GitHub Copilot | [`.github/copilot-instructions.md`](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions) |
| Gemini CLI | [`GEMINI.md`](https://geminicli.com/docs/cli/gemini-md/) |

```md
## Feature completion

After implementing a feature and before its final commit or pull request, use the installed
Vibemin skill on the complete feature diff from its merge-base with the target branch
(normally `origin/main`).

- Derive the fastest relevant non-mutating tests, lint, formatter-check, and strict typecheck
  commands from this repository; preview with `--dry-run` before applying.
- Keep tests, manifests and lockfiles, snapshots, and visual assets protected unless their
  dedicated strength or preservation oracle is available.
- Add a focused security check for authentication, authorization, tenant, session, token, or
  secret changes. Use the broad suite or clean-install validation as a final check.
- Apply the reduction only when the original feature passes, then review the resulting diff
  and rerun the relevant suite in the real checkout.
- Never weaken tests, remove required behavior, or change acceptance criteria merely to make
  the patch smaller.
```

This makes Vibemin a final evidence-driven cleanup pass, not something that fights the agent
while the feature is still taking shape.

### Run it directly

From the repository containing your changes:

```sh
vibemin --feature-base origin/main \
  --check "npm test -- --run" \
  --check "npm run lint" \
  --check "npm run typecheck"
```

The verified result is written back as working-tree changes, ready to review and commit.
Add `--dry-run` to inspect what Vibemin would remove without changing the checkout.

### Alternative: Python package

Install directly from GitHub with [`uv`](https://docs.astral.sh/uv/):

```sh
uv tool install git+https://github.com/francescoVaglienti/vibemin.git
```

## Built for agentic code

| Capability | What it gives you |
| --- | --- |
| **Feature-wide reduction** | Minimize committed and uncommitted work together from a branch merge-base. |
| **Behavior-preserving search** | Every accepted candidate must pass the checks you supplied. |
| **Safe test reduction** | Tests stay fixed unless you opt in with collection or mutation-strength protection. |
| **Visual protection** | Styles and assets stay fixed without a deterministic rendered-output oracle. |
| **Dependency protection** | Manifests and lockfiles require an explicit consistency check before reduction. |
| **Type and security gates** | TypeScript and security-sensitive changes require the checks that can actually validate them. |
| **Local by design** | No service, account, telemetry, or runtime dependency is required. |

## How it works

1. **Read the diff.** Vibemin turns inserted and deleted lines into removable units.
2. **Build a sandbox.** Candidate patches run in a temporary detached Git worktree.
3. **Search by subtraction.** Groups of units are removed using delta debugging.
4. **Verify every candidate.** Tests, linters, type checks, and output contracts decide what survives.
5. **Apply once.** Only the final verified patch is written to your checkout.

The result is *1-minimal under the supplied checks*: no remaining individual unit was
shown to be removable. It is not a claim that the implementation is globally shortest,
and weak checks can still permit an incorrect reduction.

## Safety model

Green unit tests alone do not prove that tests, lockfiles, or rendered output survived.
Vibemin protects the easy-to-game parts of a patch by default.

| Change category | Default | Explicit unlock |
| --- | --- | --- |
| Tests, specs, snapshots | Protected | `--reduce-tests` plus `--test-strength-check` or `--preserve-output` |
| Dependency manifests and lockfiles | Protected | `--allow-dependency-changes` plus `--dependency-check` |
| Styles, fonts, icons, images | Protected | `--allow-visual-changes` plus deterministic `--preserve-output` |
| TypeScript | Typecheck required | `--allow-untyped-typescript` |
| Auth, tenant, token, session, secret code | Security oracle required | `--security-check` |
| Expensive broad validation | Run once on the winner | `--final-check` |

These defaults prevent misleading wins such as deleting assertions until the suite passes,
removing CSS because a non-visual build stays green, or drifting a lockfile away from its
manifest. Vibemin reports every protected file as fixed context.

## Recipes

### Minimize selected paths

```sh
vibemin src/new-feature \
  --check "npm test -- --run tests/new-feature.test.ts" \
  --check "npm run lint"
```

### Minimize a whole feature

`--feature-base` finds the merge-base, so unrelated target-branch history is excluded.
Use `--base REF` when you want an exact baseline instead.

```sh
vibemin --feature-base origin/main \
  --check "pytest -q" \
  --final-check "pytest -q tests/integration"
```

### Reduce tests without weakening them

Preserve the collected test inventory when simplifying test bodies:

```sh
vibemin tests --reduce-tests \
  --check "pytest -q" \
  --preserve-output "pytest --collect-only -q | sed '/collected in/d'"
```

When intentionally merging overlapping cases, collection output must change. Protect the
mutation score or killed-mutant set instead:

```sh
vibemin tests --reduce-tests \
  --check "pytest -q" \
  --test-strength-check "./scripts/check-mutation-baseline"
```

Coverage alone does not preserve assertion strength.

### Preserve a rendered contract

```sh
vibemin web/src --allow-visual-changes \
  --check "npm run build" \
  --preserve-output "./scripts/render-reference-screenshot --hash"
```

`--preserve-output` records deterministic stdout and stderr from the first verified
candidate and requires an exact match from every smaller one. It also works well for API
schemas, generated interfaces, and CLI snapshots.

### Validate dependency changes

```sh
vibemin pyproject.toml uv.lock --allow-dependency-changes \
  --check "pytest -q" \
  --dependency-check "uv lock --check"
```

### Preview without applying

```sh
vibemin --dry-run \
  --check "pytest -q" \
  --check "ruff check ."
```

## CLI essentials

| Option | Purpose |
| --- | --- |
| `-c, --check COMMAND` | Add a fast, non-mutating acceptance check; repeatable and required. |
| `-p, --preserve-output COMMAND` | Preserve deterministic command output exactly. |
| `--final-check COMMAND` | Run an expensive clean-install or broad check on the winner. |
| `--feature-base REF` | Include the entire feature since `merge-base HEAD REF`. |
| `--base REF` | Use an exact baseline instead of `HEAD`. |
| `--max-attempts N` | Bound the number of candidate checks; defaults to 500. |
| `--timeout SECONDS` | Bound each command; defaults to 300 seconds. |
| `--dry-run` | Find the result without changing the checkout. |
| `--verbose` | Show output from failed candidate checks. |

Run `vibemin --help` for the complete command reference.

## Guardrails and limitations

- Staged changes are rejected so the index and working tree cannot diverge unexpectedly.
- Symlinks and changed directories or submodules are currently rejected.
- Ignored local files such as `.env`, `.venv`, and `node_modules` are not copied into the
  temporary worktree. Prefer globally available tools or shared package-manager caches.
- Checks must be non-mutating and run from the root of the temporary worktree.
- Untracked, non-ignored files are included. Files outside explicit path arguments remain
  available as fixed context.
- Binary files and empty-file changes are atomic reduction units.

Always review the final diff. Vibemin knows only what the checks prove.

## Use it with your coding agent

Vibemin is a standalone CLI; no AI subscription or agent is required. The optional Agent
Skill teaches your existing coding agent when to minimize a patch and which test, security,
TypeScript, visual, and lockfile guardrails to preserve.

Install the CLI and skill directly:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh
```

Or install from a checkout when developing Vibemin itself:

```sh
git clone https://github.com/francescoVaglienti/vibemin.git
cd vibemin
./scripts/install-user.sh
```

The installer detects `claude`, `codex`, `copilot`, and `gemini` executables and their
local configuration directories. One match is selected automatically; several matches
produce a choice prompt. With no detected agent, Vibemin installs as a standalone CLI and
does not create an agent skill directory.

For scripts and unattended setup, make the choice explicit:

```sh
./scripts/install-user.sh --agent standalone
./scripts/install-user.sh --agent all
./scripts/install-user.sh --agent claude
./scripts/install-user.sh --agent codex
./scripts/install-user.sh --agent copilot
./scripts/install-user.sh --agent gemini
```

| Agent | Personal skill location | Use it |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/vibemin/SKILL.md` | Run `/vibemin` or let Claude select it when relevant. |
| Codex | `~/.agents/skills/vibemin/SKILL.md` | Mention `$vibemin` or let Codex select it when relevant. |
| GitHub Copilot | `~/.agents/skills/vibemin/SKILL.md` | Ask Copilot to use Vibemin on the current patch. |
| Gemini CLI | `~/.agents/skills/vibemin/SKILL.md` | Ask Gemini to minimize the patch; use `/skills list` to verify discovery. |

The skill is based on the open Agent Skills format. Codex, Copilot, and Gemini share the
same personal skill location, so the installer does not create three duplicate copies. An
explicit agent choice is safe even when that host is absent: the skill is simply ready for
its next launch.

In standalone mode you run `vibemin` directly and supply the checks on the command line;
there is no model, API key, or agent involved:

```sh
vibemin --check "pytest -q" --check "ruff check ."
```

## Development

```sh
git clone https://github.com/francescoVaglienti/vibemin.git
cd vibemin
uv run --with pytest pytest -q
uv run --with ruff ruff check .
uv run --with ruff ruff format --check .
```

The suite favors integration evidence over internal implementation tests: it exercises real
Git repositories, runs release executables end to end, and makes Vibemin minimize its own
source while its focused test suite acts as the oracle.

Source installs target Python 3.10+ and have no runtime dependencies. Release executables
bundle their own Python runtime.

## License

[MIT](LICENSE) © Francesco Vaglienti
