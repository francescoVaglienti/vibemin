<div align="center">
  <img src="assets/vibemin-hero.svg" alt="Vibemin. Make every line earn its place" width="100%">
</div>

<div align="center">

[![CI](https://github.com/francescoVaglienti/vibemin/actions/workflows/ci.yml/badge.svg)](https://github.com/francescoVaglienti/vibemin/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/francescoVaglienti/vibemin?color=6D5EF5)](https://github.com/francescoVaglienti/vibemin/releases/latest)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero runtime dependencies](https://img.shields.io/badge/runtime_dependencies-0-6D5EF5)](pyproject.toml)
[![MIT](https://img.shields.io/badge/license-MIT-0F766E)](LICENSE)

**Test-guided minimization for AI-generated Git diffs.**

Vibemin removes code your checks cannot justify—and keeps the patch that survives.

It works with Claude Code, Codex, GitHub Copilot, Gemini CLI, or without an agent.

[Quick start](#quick-start) · [How it works](#how-it-works) · [Safety](#safety) · [Agent setup](#agent-setup)

</div>

---

AI coding tools are very good at adding code. They are terrible at taking it back out.
Vibemin treats the diff as a search space and your checks as the contract. It keeps removing
parts of the change until removing anything else would make a check fail.

> The checks are the contract. The diff is negotiable.

```console
$ vibemin --feature-base origin/main \
    --check "pytest -q" \
    --check "ruff check ."

[001] PASS  retained=11844  1.42s
[027] fail  retained=10320  1.31s
[149] PASS  retained=9620   1.26s

Removed 2,224 of 11,844 diff units in 149 checks; 9,620 remain.
```

Everything runs locally in a disposable Git worktree. Your code is not sent anywhere. The
real checkout is updated once, after the final result has passed every check you supplied.

## Quick start

### I do not care, just fix my agent setup

On macOS or Linux, run this:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh -s -- --everything
```

This installs the standalone CLI, checks its checksum, finds Claude Code, Codex, GitHub
Copilot and Gemini CLI, then installs the Vibemin skill for every host it finds. It also adds
one short rule to each host so Vibemin runs after a feature is built. That rule tells the
agent to derive the relevant test, type, security, visual and lockfile checks from the
repository.

You can run the command again later. It refreshes the skill and does not duplicate the rule.
If there is no supported agent on the machine, it only installs the CLI. Restart any open
agent sessions once after installation so they can discover the skill.

### Choose the setup yourself

Install only the CLI. This does not need Python and does not change any agent configuration:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-binary.sh | sh
```

Install the CLI and the skill for detected agents, without changing their instructions:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh
```

Choose one host:

```sh
# claude, codex, copilot, or gemini
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh -s -- --agent codex
```

Choose one host and make it run Vibemin when it finishes a feature:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh -s -- --agent codex --configure
```

Prepare all four hosts, including hosts that are not installed yet:

```sh
curl -fsSL https://raw.githubusercontent.com/francescoVaglienti/vibemin/main/scripts/install-agent.sh | sh -s -- --agent all --configure
```

Or install the Python package from [PyPI](https://pypi.org/project/vibemin/):

```sh
uv tool install vibemin
```

Executables for macOS, Linux and Windows are available on the
[Releases page](https://github.com/francescoVaglienti/vibemin/releases/latest).

### Choose what to reduce

Vibemin removes lines from the difference between the current checkout and a baseline. The
baseline decides what is in scope:

| Goal | Baseline | Command |
| --- | --- | --- |
| Current uncommitted work | `HEAD` | `vibemin PATHS ...` |
| An existing feature | Branch split from the target | `vibemin --feature-base origin/main ...` |
| The whole codebase | A temporary empty commit | `vibemin --base "$EMPTY_BASE" ...` |

#### Reduce an existing feature

Run this from the feature branch. It includes every committed and uncommitted change since
the branch split from `origin/main`:

```sh
vibemin --feature-base origin/main --dry-run \
  --check "npm test -- --run" \
  --check "npm run lint" \
  --check "npm run typecheck"
```

Review the proposal, then run the same command without `--dry-run` to apply it. The verified
result is written back as working tree changes. Existing commits are not rewritten. You can
review the result and then amend or squash the feature yourself.

#### Reduce the whole codebase

To put every tracked file in scope, compare the current checkout with a temporary empty
commit:

```sh
EMPTY_TREE=$(git hash-object -t tree /dev/null)
EMPTY_BASE=$(git -c user.name=Vibemin -c user.email=vibemin@localhost \
  commit-tree "$EMPTY_TREE" -m "Empty Vibemin baseline")

vibemin --base "$EMPTY_BASE" --dry-run \
  --check "pytest -q" \
  --check "ruff check ."
```

The empty commit is not added to your branch or its history. With no path arguments, Vibemin
can try every unprotected line in the repository. Tests, dependency files and visual assets
stay fixed by default. Use complete checks here because the search covers the complete
codebase. Review the proposal, then remove `--dry-run` to apply it.

When you use the agent skill, the agent derives the commands and any extra guards from the
repository.

## What it protects

| Capability | Result |
| --- | --- |
| Entire feature | Minimize committed and uncommitted work together from the branch merge base. |
| Verified reduction | Every accepted candidate must pass the checks you supplied. |
| Tests | Keep tests fixed unless you explicitly allow reduction and protect their strength. |
| Visual output | Keep styles and assets fixed unless you supply a deterministic output check. |
| Dependencies | Require a consistency check before manifests or lockfiles may change. |
| Types and security | Require checks that can validate TypeScript and security sensitive changes. |
| Local execution | Use no service, account, telemetry or runtime dependency. |

## How it works

1. Read the diff:
   Inserted and deleted lines become units that Vibemin can try to remove.
2. Build a sandbox:
   Every candidate patch runs in a temporary detached Git worktree.
3. Search by subtraction:
   Delta debugging removes groups of units and keeps the smaller candidates that still pass.
4. Verify each candidate:
   Tests, linters, type checks and output contracts decide what survives.
5. Apply once:
   Only the final verified patch is written to the real checkout.

The result is one minimal under the checks you supplied. Vibemin has shown that no individual
unit can be removed while those checks still pass. It does not claim that the implementation
is the shortest possible one. Weak checks can still allow a wrong reduction, which is why the
guards below exist.

## Safety

Green unit tests do not prove that tests, lockfiles or rendered output survived. Vibemin keeps
the parts that are easy to game fixed by default.

| Change category | Default | How to allow it |
| --- | --- | --- |
| Tests, specs and snapshots | Protected | `--reduce-tests` plus `--test-strength-check` or `--preserve-output` |
| Dependency manifests and lockfiles | Protected | `--allow-dependency-changes` plus `--dependency-check` |
| Styles, fonts, icons and images | Protected | `--allow-visual-changes` plus deterministic `--preserve-output` |
| TypeScript | Typecheck required | `--allow-untyped-typescript` |
| Auth, tenant, token, session and secret code | Security check required | `--security-check` |
| Expensive broad validation | Run once on the winner | `--final-check` |

These defaults stop misleading wins such as deleting assertions until the suite passes,
removing CSS because a build does not inspect the result, or leaving a lockfile out of sync
with its manifest. Vibemin reports protected files as fixed context so the reason is visible.

## Recipes

### Reduce current uncommitted changes

Without `--base` or `--feature-base`, Vibemin compares the working tree with `HEAD`. Path
arguments limit that uncommitted diff to the files or directories you name:

```sh
vibemin src/new-feature \
  --check "npm test -- --run tests/new-feature.test.ts" \
  --check "npm run lint"
```

### Limit an existing feature to selected paths

Combine path arguments with `--feature-base` when only part of an existing feature should be
reduced. Other feature files remain available to the checks as fixed context:

```sh
vibemin src/new-feature --feature-base origin/main \
  --check "pytest -q" \
  --final-check "pytest -q tests/integration"
```

### Reduce tests without weakening them

If you simplify test bodies, preserve the collected test inventory:

```sh
vibemin tests --reduce-tests \
  --check "pytest -q" \
  --preserve-output "pytest --collect-only -q | sed '/collected in/d'"
```

If you intentionally merge overlapping cases, the collection output has to change. Protect
the mutation score or killed mutant set instead:

```sh
vibemin tests --reduce-tests \
  --check "pytest -q" \
  --test-strength-check "./scripts/check-mutation-baseline"
```

Coverage by itself does not protect assertion strength.

### Preserve rendered output

```sh
vibemin web/src --allow-visual-changes \
  --check "npm run build" \
  --preserve-output "./scripts/render-reference-screenshot --hash"
```

`--preserve-output` records deterministic output from the first verified candidate and
requires an exact match from every smaller candidate. The same approach works for API
schemas, generated interfaces and CLI snapshots.

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
| `-c, --check COMMAND` | Add a fast check that does not change files. Repeatable and required. |
| `-p, --preserve-output COMMAND` | Preserve deterministic command output exactly. |
| `--final-check COMMAND` | Run an expensive clean install or broad check on the winner. |
| `--feature-base REF` | Include the entire feature since the merge base of `HEAD` and `REF`. |
| `--base REF` | Use an exact baseline instead of `HEAD`. |
| `--max-attempts N` | Limit candidate checks. The default is 500. |
| `--timeout SECONDS` | Limit each command. The default is 300 seconds. |
| `--dry-run` | Find the result without changing the checkout. |
| `--verbose` | Show output from failed candidate checks. |

Run `vibemin --help` for the complete command reference.

## Current limits

1. Staged changes are rejected because the index and working tree should not diverge during a run.
2. Symlinks and changed directories or submodules are currently rejected.
3. Ignored local files such as `.env`, `.venv` and `node_modules` are not copied into the temporary worktree. Use tools that are globally available or a shared package manager cache.
4. Checks must run from the temporary worktree root and must not change files.
5. Untracked files are included when Git does not ignore them. Files outside the selected paths stay available as fixed context.
6. Binary files and empty file changes are reduced as single units.

Review the final diff. Vibemin can only prove what the supplied checks prove.

## Agent setup

Agent integration has two parts. The skill tells an agent how to minimize safely. The optional
feature completion rule tells it when to do so. Vibemin itself stays a local CLI. It does not
need a model API, an account or telemetry.

The installer only appends a marked Vibemin block to an existing instruction file. It does
not rewrite the content that is already there, and running it again does not duplicate the
block.

| Agent | Personal skill | Instruction added by `--configure` |
| --- | --- | --- |
| Claude Code | `~/.claude/skills/vibemin/SKILL.md` | `~/.claude/CLAUDE.md` |
| Codex | `~/.agents/skills/vibemin/SKILL.md` | `~/.codex/AGENTS.md` |
| GitHub Copilot | `~/.agents/skills/vibemin/SKILL.md` | `~/.copilot/copilot-instructions.md` |
| Gemini CLI | `~/.agents/skills/vibemin/SKILL.md` | `~/.gemini/GEMINI.md` |

Codex, Copilot and Gemini use the same Agent Skills location, so the installer keeps one copy
for the three hosts. Claude uses its own skill directory. Choosing a host that is not
installed yet is allowed. The files will be ready when that host starts.

### Installer modes

| Mode | Result |
| --- | --- |
| No arguments | Detect installed hosts and install their skill. Ask which host to use when several are found in an interactive terminal. |
| `--everything` | Install and configure every detected host without asking. |
| `--agent codex` | Install for one named host, even when it is not installed yet. |
| `--agent codex --configure` | Install one host and add its feature completion rule. |
| `--agent all --configure` | Prepare every supported host. |
| `--agent standalone` | Install only the CLI. |

Accepted host names are `claude`, `codex`, `copilot` and `gemini`. The same options work with
the curl command and with `scripts/install-user.sh` from a checkout.

### Share the rule with a team

`--configure` changes the current machine. If every contributor should use Vibemin after a
feature, commit the same short rule to the repository instruction file for each host you use:

| Agent | Repository instruction file |
| --- | --- |
| Claude Code | [`CLAUDE.md`](https://code.claude.com/docs/en/memory#claudemd-files) |
| Codex | [`AGENTS.md`](https://learn.chatgpt.com/docs/agent-configuration/agents-md) |
| GitHub Copilot | [`.github/copilot-instructions.md`](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions) |
| Gemini CLI | [`GEMINI.md`](https://geminicli.com/docs/cli/gemini-md/) |

The rule only needs to say when Vibemin should run. The installed skill owns the detailed
procedure, including how to derive checks and protect sensitive files.

### Install from source

Use a checkout when you are changing Vibemin itself:

```sh
git clone https://github.com/francescoVaglienti/vibemin.git
cd vibemin
./scripts/install-user.sh
```

Standalone use has no model or agent involved. Supply the checks on the command line:

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

The test suite focuses on integration evidence. It creates real Git repositories, runs the
release executables and makes Vibemin minimize its own source while a focused test suite acts
as the oracle.

Source installs support Python 3.10 and newer and have no runtime dependencies. Release
executables include their own Python runtime.

## License

[MIT](LICENSE) © Francesco Vaglienti
