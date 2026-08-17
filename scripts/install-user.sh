#!/bin/sh
set -eu

usage() {
    cat <<'EOF'
Usage: ./scripts/install-user.sh [--agent all|claude|codex|copilot|gemini]

Install the Vibemin Agent Skill for one supported coding agent or all of them.
The default is all. The vibemin CLI must be installed separately.
EOF
}

SELECTED_AGENT=all
while [ "$#" -gt 0 ]; do
    case "$1" in
        --agent)
            if [ "$#" -lt 2 ]; then
                printf '%s\n' 'install-user.sh: --agent requires a value' >&2
                exit 2
            fi
            SELECTED_AGENT=$2
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

case "$SELECTED_AGENT" in
    all|claude|codex|copilot|gemini) ;;
    *)
        printf 'install-user.sh: unsupported agent: %s\n' "$SELECTED_AGENT" >&2
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
MAN_ROOT=${XDG_DATA_HOME:-"$USER_ROOT/.local/share"}
MAN_DIR="$MAN_ROOT/man/man1"

install_skill() {
    destination=$1
    mkdir -p "$destination/agents"
    install -m 0644 "$SOURCE_SKILL/SKILL.md" "$destination/SKILL.md"
    install -m 0644 "$SOURCE_SKILL/agents/openai.yaml" "$destination/agents/openai.yaml"
}

case "$SELECTED_AGENT" in
    all)
        install_skill "$CLAUDE_SKILL_DIR"
        install_skill "$SHARED_SKILL_DIR"
        printf 'Installed for Claude Code: %s\n' "$CLAUDE_SKILL_DIR/SKILL.md"
        printf 'Installed for Codex, GitHub Copilot, and Gemini CLI: %s\n' \
            "$SHARED_SKILL_DIR/SKILL.md"
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

mkdir -p "$MAN_DIR"
install -m 0644 "$PROJECT_DIR/docs/vibemin.1" "$MAN_DIR/vibemin.1"
printf 'Installed man page: %s\n' "$MAN_DIR/vibemin.1"
printf 'If man cannot find it, run: man -M %s/man vibemin\n' "$MAN_ROOT"
