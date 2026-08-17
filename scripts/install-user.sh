#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Usage: ./scripts/install-user.sh [--everything] [--configure]
       [--agent auto|all|standalone|claude|codex|copilot|gemini]

Install Vibemin and its optional Agent Skill. By default, the installer detects supported
coding agents, selects the only match, or asks when several are available. With no detected
agent, it installs Vibemin as a standalone CLI. --everything detects installed agents,
installs their skills, and adds an idempotent global feature-completion instruction.
EOF
}

REQUESTED_AGENT=auto
CONFIGURE_COMPLETION=0
AUTO_ACCEPT_DETECTED=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --everything)
            REQUESTED_AGENT=auto
            CONFIGURE_COMPLETION=1
            AUTO_ACCEPT_DETECTED=1
            shift
            ;;
        --configure)
            CONFIGURE_COMPLETION=1
            shift
            ;;
        --agent)
            if [ "$#" -lt 2 ]; then
                printf '%s\n' 'install-user.sh: --agent requires a value' >&2
                exit 2
            fi
            REQUESTED_AGENT=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'install-user.sh: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "$REQUESTED_AGENT" in
    auto|all|standalone|claude|codex|copilot|gemini) ;;
    *)
        printf 'install-user.sh: unsupported agent: %s\n' "$REQUESTED_AGENT" >&2
        usage >&2
        exit 2
        ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
SOURCE_SKILL="$PROJECT_DIR/integrations/skills/vibemin"
USER_ROOT=${VIBEMIN_USER_HOME:-"$HOME"}
SHARED_SKILL_DIR=${VIBEMIN_AGENT_SKILLS_DIR:-"$USER_ROOT/.agents/skills/vibemin"}
CLAUDE_ROOT=${CLAUDE_CONFIG_DIR:-"$USER_ROOT/.claude"}
CLAUDE_SKILL_DIR="$CLAUDE_ROOT/skills/vibemin"
CODEX_ROOT="$USER_ROOT/.codex"
COPILOT_ROOT=${COPILOT_HOME:-"$USER_ROOT/.copilot"}
GEMINI_ROOT="$USER_ROOT/.gemini"

agent_is_installed() {
    agent_command=$1
    agent_config_dir=$2
    if [ "${VIBEMIN_SKIP_COMMAND_DETECTION:-0}" != 1 ] && \
        command -v "$agent_command" >/dev/null 2>&1; then
        return 0
    fi
    [ -d "$agent_config_dir" ]
}

DETECTED_AGENTS=
DETECTED_COUNT=0
if agent_is_installed claude "$CLAUDE_ROOT"; then
    DETECTED_AGENTS="$DETECTED_AGENTS claude"
    DETECTED_COUNT=$((DETECTED_COUNT + 1))
fi
if agent_is_installed codex "$CODEX_ROOT"; then
    DETECTED_AGENTS="$DETECTED_AGENTS codex"
    DETECTED_COUNT=$((DETECTED_COUNT + 1))
fi
if agent_is_installed copilot "$COPILOT_ROOT"; then
    DETECTED_AGENTS="$DETECTED_AGENTS copilot"
    DETECTED_COUNT=$((DETECTED_COUNT + 1))
fi
if agent_is_installed gemini "$GEMINI_ROOT"; then
    DETECTED_AGENTS="$DETECTED_AGENTS gemini"
    DETECTED_COUNT=$((DETECTED_COUNT + 1))
fi
DETECTED_AGENTS=${DETECTED_AGENTS# }

is_detected() {
    case " $DETECTED_AGENTS " in
        *" $1 "*) return 0 ;;
        *) return 1 ;;
    esac
}

choose_detected_agent() {
    while :; do
        printf 'Detected coding agents: %s\n' "$DETECTED_AGENTS"
        printf 'Install for which agent? [%s, all, standalone]: ' "$DETECTED_AGENTS"
        if ! IFS= read -r answer; then
            printf '\nNo input available; installing for every detected agent.\n'
            SELECTED_AGENT=detected
            return
        fi
        case "$answer" in
            all)
                SELECTED_AGENT=detected
                return
                ;;
            standalone)
                SELECTED_AGENT=standalone
                return
                ;;
            claude|codex|copilot|gemini)
                if is_detected "$answer"; then
                    SELECTED_AGENT=$answer
                    return
                fi
                ;;
        esac
        printf 'Choose one of the detected agents, all, or standalone.\n' >&2
    done
}

SELECTED_AGENT=$REQUESTED_AGENT
if [ "$REQUESTED_AGENT" = auto ]; then
    case "$DETECTED_COUNT" in
        0)
            SELECTED_AGENT=standalone
            printf 'No supported coding agent detected; using standalone mode.\n'
            ;;
        1)
            set -- $DETECTED_AGENTS
            SELECTED_AGENT=$1
            printf 'Detected %s; selecting it automatically.\n' "$SELECTED_AGENT"
            ;;
        *)
            if [ "$AUTO_ACCEPT_DETECTED" = 1 ]; then
                SELECTED_AGENT=detected
                printf 'Detected %s; installing and configuring all of them.\n' \
                    "$DETECTED_AGENTS"
            elif [ -t 0 ] || [ "${VIBEMIN_FORCE_INTERACTIVE:-0}" = 1 ]; then
                choose_detected_agent
            else
                SELECTED_AGENT=detected
                printf 'Detected %s; non-interactive setup will install for all of them.\n' \
                    "$DETECTED_AGENTS"
            fi
            ;;
    esac
elif [ "$REQUESTED_AGENT" != all ] && [ "$REQUESTED_AGENT" != standalone ] && \
    ! is_detected "$REQUESTED_AGENT"; then
    printf '%s is not currently detected; its skill will be ready when it is installed.\n' \
        "$REQUESTED_AGENT"
fi

ensure_cli() {
    if command -v vibemin >/dev/null 2>&1; then
        printf 'Vibemin CLI already available: %s\n' "$(command -v vibemin)"
        return 0
    fi
    if [ "${VIBEMIN_SKIP_CLI_INSTALL:-0}" = 1 ]; then
        printf 'Skipped Vibemin CLI installation for this validation run.\n'
        return 0
    fi
    if ! command -v uv >/dev/null 2>&1; then
        return 1
    fi
    printf 'Installing the standalone Vibemin CLI with uv...\n'
    uv tool install "$PROJECT_DIR"
}

if ! ensure_cli; then
    printf '%s\n' 'Could not install the Vibemin CLI because uv is unavailable.' >&2
    printf '%s\n' 'Install uv from https://docs.astral.sh/uv/, then rerun this command.' >&2
    if [ "$SELECTED_AGENT" = standalone ]; then
        exit 2
    fi
    printf '%s\n' 'The agent skill will still be installed, but it needs the vibemin command.' >&2
fi

install_skill() {
    destination=$1
    mkdir -p "$destination/agents"
    install -m 0644 "$SOURCE_SKILL/SKILL.md" "$destination/SKILL.md"
    install -m 0644 "$SOURCE_SKILL/agents/openai.yaml" "$destination/agents/openai.yaml"
}

install_detected_skills() {
    if is_detected claude; then
        install_skill "$CLAUDE_SKILL_DIR"
        printf 'Installed for Claude Code: %s\n' "$CLAUDE_SKILL_DIR/SKILL.md"
    fi
    if is_detected codex || is_detected copilot || is_detected gemini; then
        install_skill "$SHARED_SKILL_DIR"
        printf 'Installed shared Agent Skill: %s\n' "$SHARED_SKILL_DIR/SKILL.md"
    fi
}

configure_feature_completion() {
    destination=$1
    agent_name=$2
    marker='<!-- vibemin:feature-completion -->'
    if [ -f "$destination" ] && grep -F "$marker" "$destination" >/dev/null 2>&1; then
        printf 'Feature completion already configured for %s: %s\n' \
            "$agent_name" "$destination"
        return
    fi
    mkdir -p "$(dirname -- "$destination")"
    if [ -s "$destination" ]; then
        printf '\n' >> "$destination"
    fi
    cat >> "$destination" <<'EOF'
<!-- vibemin:feature-completion -->
## Vibemin feature completion

After implementing a feature and before its final commit or pull request, use the installed
Vibemin skill on the complete feature diff from its merge-base with the target branch.
Derive relevant non-mutating tests, lint, formatter-check, strict typecheck, and focused
security checks from the repository. Preview before applying; keep tests, lockfiles,
snapshots, and visual assets protected without their dedicated oracle. Apply only when the
original feature passes, then review the diff and rerun the relevant suite. Never weaken
tests or required behavior merely to make the patch smaller.
EOF
    printf 'Configured feature completion for %s: %s\n' "$agent_name" "$destination"
}

configure_detected_agents() {
    if is_detected claude; then
        configure_feature_completion "$CLAUDE_ROOT/CLAUDE.md" 'Claude Code'
    fi
    if is_detected codex; then
        configure_feature_completion "$CODEX_ROOT/AGENTS.md" Codex
    fi
    if is_detected copilot; then
        configure_feature_completion "$COPILOT_ROOT/copilot-instructions.md" 'GitHub Copilot'
    fi
    if is_detected gemini; then
        configure_feature_completion "$GEMINI_ROOT/GEMINI.md" 'Gemini CLI'
    fi
}

case "$SELECTED_AGENT" in
    all)
        install_skill "$CLAUDE_SKILL_DIR"
        install_skill "$SHARED_SKILL_DIR"
        printf 'Installed for Claude Code: %s\n' "$CLAUDE_SKILL_DIR/SKILL.md"
        printf 'Installed for Codex, GitHub Copilot, and Gemini CLI: %s\n' \
            "$SHARED_SKILL_DIR/SKILL.md"
        ;;
    detected)
        install_detected_skills
        ;;
    standalone)
        printf 'Standalone setup selected; no agent skill was installed.\n'
        ;;
    claude)
        install_skill "$CLAUDE_SKILL_DIR"
        printf 'Installed for Claude Code: %s\n' "$CLAUDE_SKILL_DIR/SKILL.md"
        ;;
    codex|copilot|gemini)
        install_skill "$SHARED_SKILL_DIR"
        printf 'Installed for %s: %s\n' "$SELECTED_AGENT" "$SHARED_SKILL_DIR/SKILL.md"
        ;;
esac

if [ "$CONFIGURE_COMPLETION" = 1 ]; then
    case "$SELECTED_AGENT" in
        all)
            configure_feature_completion "$CLAUDE_ROOT/CLAUDE.md" 'Claude Code'
            configure_feature_completion "$CODEX_ROOT/AGENTS.md" Codex
            configure_feature_completion "$COPILOT_ROOT/copilot-instructions.md" \
                'GitHub Copilot'
            configure_feature_completion "$GEMINI_ROOT/GEMINI.md" 'Gemini CLI'
            ;;
        detected)
            configure_detected_agents
            ;;
        standalone)
            printf '%s\n' 'No agent feature-completion instruction was added.'
            ;;
        claude)
            configure_feature_completion "$CLAUDE_ROOT/CLAUDE.md" 'Claude Code'
            ;;
        codex)
            configure_feature_completion "$CODEX_ROOT/AGENTS.md" Codex
            ;;
        copilot)
            configure_feature_completion "$COPILOT_ROOT/copilot-instructions.md" \
                'GitHub Copilot'
            ;;
        gemini)
            configure_feature_completion "$GEMINI_ROOT/GEMINI.md" 'Gemini CLI'
            ;;
    esac
fi
