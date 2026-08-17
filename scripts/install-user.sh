#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
CLAUDE_DIR=${CLAUDE_CONFIG_DIR:-"$HOME/.claude"}
SKILL_DIR="$CLAUDE_DIR/skills/vibemin"
MAN_ROOT=${XDG_DATA_HOME:-"$HOME/.local/share"}
MAN_DIR="$MAN_ROOT/man/man1"
CLAUDE_FILE="$CLAUDE_DIR/CLAUDE.md"
IMPORT_LINE="@$CLAUDE_DIR/vibemin.md"

mkdir -p "$SKILL_DIR" "$MAN_DIR"
install -m 0644 "$PROJECT_DIR/integrations/claude/skills/vibemin/SKILL.md" "$SKILL_DIR/SKILL.md"
install -m 0644 "$PROJECT_DIR/integrations/claude/global-directive.md" "$CLAUDE_DIR/vibemin.md"
install -m 0644 "$PROJECT_DIR/docs/vibemin.1" "$MAN_DIR/vibemin.1"

touch "$CLAUDE_FILE"
if ! grep -Fqx "$IMPORT_LINE" "$CLAUDE_FILE"; then
    printf '\n%s\n' "$IMPORT_LINE" >> "$CLAUDE_FILE"
fi

printf 'Installed Claude skill: %s\n' "$SKILL_DIR/SKILL.md"
printf 'Installed Claude directive: %s\n' "$CLAUDE_DIR/vibemin.md"
printf 'Installed man page: %s\n' "$MAN_DIR/vibemin.1"
printf 'If man cannot find it, run: man -M %s/man vibemin\n' "$MAN_ROOT"
