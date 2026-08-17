#!/bin/sh
set -eu

REPOSITORY=francescoVaglienti/vibemin
SOURCE_REF=${VIBEMIN_SOURCE_REF:-main}
SOURCE_BASE_URL=${VIBEMIN_SOURCE_BASE_URL:-"https://raw.githubusercontent.com/$REPOSITORY/$SOURCE_REF"}
SOURCE_QUERY=
case "$SOURCE_BASE_URL" in
    https://raw.githubusercontent.com/*) SOURCE_QUERY="?v=$(date +%s)" ;;
esac

for required_command in curl mktemp; do
    if ! command -v "$required_command" >/dev/null 2>&1; then
        printf 'Required command is unavailable: %s\n' "$required_command" >&2
        exit 2
    fi
done

TEMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/vibemin-agent-install.XXXXXX")
trap 'rm -rf "$TEMP_DIR"' EXIT HUP INT TERM
BUNDLE="$TEMP_DIR/vibemin"
SKILL="$BUNDLE/integrations/skills/vibemin"
mkdir -p "$BUNDLE/scripts" "$SKILL/agents"

download() {
    relative_path=$1
    destination=$2
    curl --fail --location --silent --show-error \
        "$SOURCE_BASE_URL/$relative_path$SOURCE_QUERY" --output "$destination"
}

if [ "${VIBEMIN_SKIP_BINARY_INSTALL:-0}" != 1 ]; then
    download scripts/install-binary.sh "$BUNDLE/scripts/install-binary.sh"
    sh "$BUNDLE/scripts/install-binary.sh"
fi

INSTALL_DIR=${VIBEMIN_INSTALL_DIR:-"$HOME/.local/bin"}
PATH="$INSTALL_DIR:$PATH"
export PATH

download scripts/install-user.sh "$BUNDLE/scripts/install-user.sh"
download integrations/skills/vibemin/SKILL.md "$SKILL/SKILL.md"
download integrations/skills/vibemin/agents/openai.yaml "$SKILL/agents/openai.yaml"

VIBEMIN_SKIP_CLI_INSTALL=1 sh "$BUNDLE/scripts/install-user.sh" "$@"
